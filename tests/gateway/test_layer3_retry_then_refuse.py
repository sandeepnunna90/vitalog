"""Unit tests for Layer 3 retry-then-refuse logic (AC2, AC4)."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

from src.gateway.errors import OutputValidationError


class Greeting(BaseModel):
    message: str


def _make_tool_response(tool_input: dict[str, Any]) -> MagicMock:
    block = MagicMock()
    block.type = "tool_use"
    block.input = tool_input
    response = MagicMock()
    response.content = [block]
    response.stop_reason = "tool_use"
    response.usage.input_tokens = 10
    response.usage.output_tokens = 5
    return response


def _setup_gateway(prompts_dir: Path, phrases: list[str] | None = None) -> Any:
    """Return a Gateway wired to a temp prompts_dir with custom banned phrases."""
    from src.gateway.gateway import Gateway
    from src.gateway.guardrails.layer3_deterministic import Layer3

    shared = prompts_dir / "_shared"
    shared.mkdir(exist_ok=True)
    content = "\n".join(phrases or []) + "\n"
    (shared / "banned_phrases.txt").write_text(content, encoding="utf-8")

    gw = Gateway(prompts_dir=prompts_dir, api_key="test-key")
    gw._layer3 = Layer3(prompts_dir=prompts_dir)
    return gw


# ── Banned-phrase retry ───────────────────────────────────────────────────────


def test_banned_phrase_retry_succeeds(prompts_dir: Path) -> None:
    """First response contains banned phrase; second is clean → success, 2 adapter calls."""
    gw = _setup_gateway(prompts_dir, phrases=["you should"])

    call_count = 0

    def _flaky(*args: Any, **kwargs: Any) -> MagicMock:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _make_tool_response({"message": "You should see a doctor."})
        return _make_tool_response({"message": "Your labs look stable."})

    with patch.object(gw._adapter._client.messages, "create", side_effect=_flaky):
        result = gw.call("hello", "v1", {"name": "Mark"}, Greeting)

    assert result.message == "Your labs look stable."
    assert call_count == 2


def test_banned_phrase_retry_exhausted_raises_output_validation_error(prompts_dir: Path) -> None:
    """Both attempts contain banned phrase → OutputValidationError, no partial result."""
    gw = _setup_gateway(prompts_dir, phrases=["you should"])

    with patch.object(
        gw._adapter._client.messages,
        "create",
        return_value=_make_tool_response({"message": "You should take insulin."}),
    ):
        with pytest.raises(OutputValidationError):
            gw.call("hello", "v1", {"name": "Mark"}, Greeting)


def test_banned_phrase_retry_system_contains_offending_phrase(prompts_dir: Path) -> None:
    """On banned-phrase retry, the system prompt must name the offending phrase."""
    gw = _setup_gateway(prompts_dir, phrases=["you should"])

    captured_systems: list[str] = []
    call_count = 0

    def _capture(*args: Any, **kwargs: Any) -> MagicMock:
        nonlocal call_count
        call_count += 1
        captured_systems.append(kwargs.get("system", ""))
        if call_count == 1:
            return _make_tool_response({"message": "You should eat less sugar."})
        return _make_tool_response({"message": "Glucose is within normal range."})

    with patch.object(gw._adapter._client.messages, "create", side_effect=_capture):
        gw.call("hello", "v1", {"name": "Mark"}, Greeting)

    assert call_count == 2
    retry_system = captured_systems[1]
    assert "you should" in retry_system.lower()
    assert "CRITICAL" in retry_system or "banned" in retry_system.lower()


# ── Schema validation retry ───────────────────────────────────────────────────


def test_schema_retry_succeeds(prompts_dir: Path) -> None:
    """First response has wrong schema; second is correct → success."""
    gw = _setup_gateway(prompts_dir, phrases=[])

    call_count = 0

    def _flaky(*args: Any, **kwargs: Any) -> MagicMock:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _make_tool_response({"wrong_field": "oops"})  # missing 'message'
        return _make_tool_response({"message": "All good."})

    with patch.object(gw._adapter._client.messages, "create", side_effect=_flaky):
        result = gw.call("hello", "v1", {"name": "Mark"}, Greeting)

    assert result.message == "All good."
    assert call_count == 2


def test_schema_retry_exhausted_raises_output_validation_error(prompts_dir: Path) -> None:
    """Both attempts produce wrong schema → OutputValidationError."""
    gw = _setup_gateway(prompts_dir, phrases=[])

    with patch.object(
        gw._adapter._client.messages,
        "create",
        return_value=_make_tool_response({"wrong_field": "bad"}),
    ):
        with pytest.raises(OutputValidationError):
            gw.call("hello", "v1", {"name": "Mark"}, Greeting)


def test_no_partial_output_on_double_failure(prompts_dir: Path) -> None:
    """OutputValidationError is raised — caller never receives partial data."""
    gw = _setup_gateway(prompts_dir, phrases=["you should"])

    with patch.object(
        gw._adapter._client.messages,
        "create",
        return_value=_make_tool_response({"message": "You should adjust your dose."}),
    ):
        with pytest.raises(OutputValidationError) as exc_info:
            gw.call("hello", "v1", {"name": "Mark"}, Greeting)

    # Exception message should reference the violation, not expose raw model output
    assert "validation" in str(exc_info.value).lower() or "banned" in str(exc_info.value).lower()
