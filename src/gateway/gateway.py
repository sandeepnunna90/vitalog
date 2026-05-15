"""AI Gateway — single chokepoint for all LLM calls.

Architecture principle P3: no service may call anthropic.Anthropic() directly.
Every LLM interaction routes through Gateway.call().

Guardrail seams (_apply_input_filters, _apply_output_validators) are
overrideable methods. B2 adds PII redaction + injection detection to
_apply_input_filters; B3/B4/B5 add banned-phrase regex, schema validation,
and citation verification to _apply_output_validators. Neither touches call().
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from src.gateway.anthropic_adapter import AnthropicAdapter
from src.gateway.errors import ModelError, OutputValidationError
from src.gateway.eval_logger import EvalLogEntry, EvalLogger, make_entry
from src.gateway.prompt_registry import PromptRegistry

# AuditLogRepository is imported lazily to avoid a hard dependency on the
# persistence layer when running Gateway unit tests without Supabase.
try:
    from src.persistence.audit_log_repository import AuditLogRepository as _AuditRepo
except ImportError:  # pragma: no cover
    _AuditRepo = None  # type: ignore[assignment,misc]


class Gateway:
    def __init__(
        self,
        prompts_dir: Path | None = None,
        audit_repo: Any | None = None,  # AuditLogRepository or None
        api_key: str | None = None,
    ) -> None:
        self._registry = PromptRegistry(prompts_dir)
        self._adapter = AnthropicAdapter(api_key)
        self._logger = EvalLogger()
        self._audit = audit_repo

    # ── Public entry point ────────────────────────────────────────────────────

    def call(
        self,
        prompt_id: str,
        version: str,
        inputs: dict[str, Any],
        output_schema: type[BaseModel],
        *,
        image_content: list[dict[str, Any]] | None = None,
    ) -> BaseModel:
        """Invoke a registered prompt and return a validated Pydantic model.

        Raises:
            PromptNotFoundError: if prompt_id/version is not registered.
            ModelError: if the Anthropic API fails after all retries.
            OutputValidationError: if the model output fails validation.
        """
        # 1. Resolve prompt (raises PromptNotFoundError if missing — before any network call)
        tmpl = self._registry.get(prompt_id, version)

        # 2. Input filters (pass-through in B1; B2 adds PII redaction + injection detection)
        filtered_inputs = self._apply_input_filters(inputs)

        # 3. Render templates
        system = tmpl.system_template.format_map(filtered_inputs)
        user_text = tmpl.user_template.format_map(filtered_inputs)

        # 4. Build user content (str or list of content blocks for vision inputs)
        user_content: str | list[dict[str, Any]]
        if image_content:
            user_content = [*image_content, {"type": "text", "text": user_text}]
        else:
            user_content = user_text

        # 5. Tool-use schema from Pydantic model
        tool_name = output_schema.__name__
        tool_schema = output_schema.model_json_schema()

        # 6. Invoke model with retry
        t0 = time.monotonic()
        raw: dict[str, Any] | None = None
        in_tok = 0
        out_tok = 0
        exc_to_raise: Exception | None = None

        try:
            raw, in_tok, out_tok = self._adapter.call(
                model=tmpl.model,
                system=system,
                user_content=user_content,
                tool_name=tool_name,
                tool_input_schema=tool_schema,
                max_tokens=tmpl.max_tokens,
            )
        except ModelError as exc:
            exc_to_raise = exc

        latency_ms = int((time.monotonic() - t0) * 1000)

        if exc_to_raise is not None:
            self._write_eval_log(
                tmpl.prompt_id,
                tmpl.version,
                tmpl.model,
                filtered_inputs,
                None,
                latency_ms,
                0,
                0,
                success=False,
                error=str(exc_to_raise),
            )
            raise exc_to_raise

        # 7. Output validators (pass-through in B1; B3/B4/B5 add regex + citation checks)
        assert raw is not None  # guaranteed: adapter raises ModelError on failure
        try:
            validated = self._apply_output_validators(raw, output_schema)
        except (OutputValidationError, ValidationError) as exc:
            self._write_eval_log(
                tmpl.prompt_id,
                tmpl.version,
                tmpl.model,
                filtered_inputs,
                raw,
                latency_ms,
                in_tok,
                out_tok,
                success=False,
                error=str(exc),
            )
            if isinstance(exc, ValidationError):
                raise OutputValidationError(str(exc)) from exc
            raise

        # 8. Eval log — success
        self._write_eval_log(
            tmpl.prompt_id,
            tmpl.version,
            tmpl.model,
            filtered_inputs,
            raw,
            latency_ms,
            in_tok,
            out_tok,
            success=True,
            error=None,
        )

        # 9. Audit log (optional — not required for unit tests without Supabase)
        if self._audit is not None:
            try:
                self._audit.record(
                    actor="system",
                    event_type="llm_call",
                    payload={
                        "prompt_id": tmpl.prompt_id,
                        "version": tmpl.version,
                        "model": tmpl.model,
                        "latency_ms": latency_ms,
                        "input_tokens": in_tok,
                        "output_tokens": out_tok,
                        "success": True,
                    },
                )
            except Exception:  # noqa: BLE001
                pass  # audit failure must never break the caller

        return validated

    # ── Guardrail seams ───────────────────────────────────────────────────────

    def _apply_input_filters(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """B2 hook: PII redaction and prompt-injection detection.

        Returns the (possibly modified) inputs dict. B1: pass-through.
        """
        return inputs

    def _apply_output_validators(
        self, raw: dict[str, Any], output_schema: type[BaseModel]
    ) -> BaseModel:
        """B3/B4/B5 hook: banned-phrase filter, schema validation, citation verifier.

        Returns a validated BaseModel instance. B1: Pydantic validation only.
        """
        return output_schema.model_validate(raw)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _write_eval_log(
        self,
        prompt_id: str,
        version: str,
        model: str,
        inputs: dict[str, Any],
        output: dict[str, Any] | None,
        latency_ms: int,
        in_tok: int,
        out_tok: int,
        success: bool,
        error: str | None,
    ) -> None:
        entry: EvalLogEntry = make_entry(
            prompt_id=prompt_id,
            version=version,
            model=model,
            inputs_redacted=inputs,
            output=output,
            latency_ms=latency_ms,
            input_tokens=in_tok,
            output_tokens=out_tok,
            success=success,
            error=error,
        )
        try:
            self._logger.log(entry)
        except Exception:  # noqa: BLE001
            pass  # eval log failure must never break the caller
