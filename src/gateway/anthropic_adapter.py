"""Anthropic SDK adapter — the ONLY file in src/ that may import anthropic.

Wraps client.messages.create() with:
- Forced tool-use (structured output via tool_choice)
- Exponential-backoff retry (up to max_retries attempts) for network errors
- Schema enforcement retry (one attempt) when model returns no tool_use block
- Image input support (for D5 vision-LLM fallback)
"""

from __future__ import annotations

import time
from typing import Any

import anthropic

from src.gateway.errors import ModelError

# Retry sleep schedule: attempt 0 → 0s, 1 → 1s, 2 → 2s
_RETRY_SLEEP: dict[int, float] = {0: 0.0, 1: 1.0, 2: 2.0}


class AnthropicAdapter:
    def __init__(self, api_key: str | None = None) -> None:
        # api_key defaults to ANTHROPIC_API_KEY env var (Anthropic SDK behaviour)
        self._client = anthropic.Anthropic(api_key=api_key)

    def call(
        self,
        model: str,
        system: str,
        user_content: str | list[dict[str, Any]],
        tool_name: str,
        tool_input_schema: dict[str, Any],
        max_tokens: int,
        max_retries: int = 3,
    ) -> tuple[dict[str, Any], int, int]:
        """Invoke the model and return (tool_input_dict, input_tokens, output_tokens).

        user_content may be a plain string or a list of Anthropic content blocks
        (used for image inputs in the D5 vision-fallback path).
        """
        tool: anthropic.types.ToolParam = {
            "name": tool_name,
            "description": f"Return structured output conforming to {tool_name}.",
            "input_schema": tool_input_schema,
        }

        last_exc: Exception | None = None
        # schema_retried is per-call, not per-attempt: one schema nudge total
        # regardless of how many network retries occur.
        schema_retried = False
        _uc: str | list[dict[str, Any]] = user_content

        for attempt in range(max_retries):
            try:
                response = self._client.messages.create(  # type: ignore[call-overload]
                    model=model,
                    max_tokens=max_tokens,
                    system=system,
                    messages=[{"role": "user", "content": _uc}],
                    tools=[tool],
                    tool_choice={"type": "tool", "name": tool_name},
                )

                for block in response.content:
                    if block.type == "tool_use":
                        raw: dict[str, Any] = block.input
                        return (
                            raw,
                            response.usage.input_tokens,
                            response.usage.output_tokens,
                        )

                # No tool_use block: schema enforcement retry (once, no sleep)
                if not schema_retried:
                    schema_retried = True
                    suffix = f"\n\nYou must call the {tool_name} tool."
                    _uc = (
                        (_uc + suffix)
                        if isinstance(_uc, str)
                        else [*_uc, {"type": "text", "text": suffix}]
                    )
                    continue

                raise ModelError(
                    f"Model returned no tool_use block after schema enforcement retry "
                    f"(stop_reason={response.stop_reason!r})"
                )

            except (
                anthropic.RateLimitError,
                anthropic.APIStatusError,
                anthropic.APIConnectionError,
            ) as exc:
                retryable = isinstance(
                    exc, (anthropic.RateLimitError, anthropic.APIConnectionError)
                ) or (isinstance(exc, anthropic.APIStatusError) and exc.status_code >= 500)
                if not retryable:
                    raise ModelError(f"Non-retryable API error: {exc}") from exc
                last_exc = exc
                if attempt < max_retries - 1:
                    time.sleep(_RETRY_SLEEP.get(attempt, 2.0**attempt))

        raise ModelError(f"Anthropic API call failed after {max_retries} attempts") from last_exc
