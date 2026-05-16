"""Unit tests for Gateway.call() — all mocked, zero network calls."""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

from src.gateway.errors import ModelError, PromptNotFoundError
from src.gateway.gateway import Gateway


class Greeting(BaseModel):
    message: str


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def prompts_dir(tmp_path: Path) -> Path:
    """Minimal prompts/ directory with hello@v1 registered."""
    registry = tmp_path / "_registry.yaml"
    registry.write_text(
        textwrap.dedent("""\
            prompts:
              - prompt_id: hello
                version: v1
                path: hello/v1.md
        """),
        encoding="utf-8",
    )
    (tmp_path / "hello").mkdir()
    (tmp_path / "hello" / "v1.md").write_text(
        textwrap.dedent("""\
            ---
            prompt_id: hello
            version: v1
            model: claude-sonnet-4-6
            max_tokens: 256
            system_template: "You are a helpful assistant."
            user_template: "Say hello to {name}."
            output_schema_name: Greeting
            ---

            # Hello Prompt
        """),
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture()
def mock_adapter_success() -> dict[str, Any]:
    """Return value for AnthropicAdapter.call on success."""
    return {"message": "Hello, Mark!"}


def _make_gateway(prompts_dir: Path, audit_repo: Any = None) -> Gateway:
    gw = Gateway(prompts_dir=prompts_dir, audit_repo=audit_repo, api_key="test-key")
    return gw


# ── AC 1: successful call returns validated model ─────────────────────────────


def test_successful_call_returns_validated_model(prompts_dir: Path) -> None:
    gw = _make_gateway(prompts_dir)
    with patch(
        "src.gateway.gateway.AnthropicAdapter.call",
        return_value=({"message": "Hello, Mark!"}, 50, 20),
    ):
        result = gw.call("hello", "v1", {"name": "Mark"}, Greeting)

    assert isinstance(result, Greeting)
    assert result.message == "Hello, Mark!"


# ── AC 2: unregistered prompt raises before any network call ──────────────────


def test_prompt_not_found_raises_before_network(prompts_dir: Path) -> None:
    gw = _make_gateway(prompts_dir)
    with patch("src.gateway.gateway.AnthropicAdapter.call") as mock_call:
        with pytest.raises(PromptNotFoundError):
            gw.call("nonexistent", "v99", {}, Greeting)
        mock_call.assert_not_called()


# ── AC 3: eval log written on success and failure ────────────────────────────


def test_eval_log_written_on_success(prompts_dir: Path, tmp_path: Path) -> None:
    from src.gateway.eval_logger import EvalLogger

    runs_dir = tmp_path / "runs"
    gw = _make_gateway(prompts_dir)
    gw._logger = EvalLogger(runs_dir)

    with patch(
        "src.gateway.gateway.AnthropicAdapter.call",
        return_value=({"message": "Hi"}, 10, 5),
    ):
        gw.call("hello", "v1", {"name": "Test"}, Greeting)

    entries = list(runs_dir.rglob("*.jsonl"))
    assert len(entries) == 1
    import json

    data = json.loads(entries[0].read_text())
    assert data["prompt_id"] == "hello"
    assert data["success"] is True
    assert data["error"] is None


def test_eval_log_written_on_failure(prompts_dir: Path, tmp_path: Path) -> None:
    from src.gateway.eval_logger import EvalLogger

    runs_dir = tmp_path / "runs"
    gw = _make_gateway(prompts_dir)
    gw._logger = EvalLogger(runs_dir)

    with patch(
        "src.gateway.gateway.AnthropicAdapter.call",
        side_effect=ModelError("boom"),
    ):
        with pytest.raises(ModelError):
            gw.call("hello", "v1", {"name": "Test"}, Greeting)

    entries = list(runs_dir.rglob("*.jsonl"))
    assert len(entries) == 1
    import json

    data = json.loads(entries[0].read_text())
    assert data["success"] is False
    assert "boom" in (data["error"] or "")


# ── AC 4: audit log recorded on success ──────────────────────────────────────


def test_audit_log_recorded_on_success(prompts_dir: Path) -> None:
    mock_audit = MagicMock()
    gw = _make_gateway(prompts_dir, audit_repo=mock_audit)

    with patch(
        "src.gateway.gateway.AnthropicAdapter.call",
        return_value=({"message": "Hi"}, 10, 5),
    ):
        gw.call("hello", "v1", {"name": "Test"}, Greeting)

    mock_audit.record.assert_called_once()
    call_kwargs = mock_audit.record.call_args
    assert call_kwargs.kwargs["event_type"] == "llm_call"
    assert call_kwargs.kwargs["actor"] == "system"
    assert call_kwargs.kwargs["payload"]["prompt_id"] == "hello"
    assert call_kwargs.kwargs["payload"]["success"] is True


# ── AC 5: retry on transient error then succeeds ─────────────────────────────


def _make_mock_response(tool_name: str, tool_input: dict[str, Any]) -> MagicMock:
    """Build a mock Anthropic Message response with a tool_use content block."""
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.input = tool_input

    response = MagicMock()
    response.content = [tool_block]
    response.stop_reason = "tool_use"
    response.usage.input_tokens = 10
    response.usage.output_tokens = 5
    return response


def test_retry_on_rate_limit_then_succeeds(prompts_dir: Path) -> None:
    import anthropic

    call_count = 0

    def _flaky(*args: Any, **kwargs: Any) -> MagicMock:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise anthropic.RateLimitError(
                message="rate limited",
                response=MagicMock(status_code=429, headers={}),
                body=None,
            )
        return _make_mock_response("Greeting", {"message": "Hello!"})

    gw = _make_gateway(prompts_dir)

    with patch("src.gateway.anthropic_adapter.time.sleep"):
        with patch.object(gw._adapter._client.messages, "create", side_effect=_flaky):
            result = gw.call("hello", "v1", {"name": "Test"}, Greeting)

    assert isinstance(result, Greeting)
    assert call_count == 2


def test_retry_exhausted_raises_model_error(prompts_dir: Path) -> None:
    import anthropic

    gw = _make_gateway(prompts_dir)

    with patch("src.gateway.anthropic_adapter.time.sleep"):
        with patch.object(
            gw._adapter._client.messages,
            "create",
            side_effect=anthropic.RateLimitError(
                message="rate limited",
                response=MagicMock(status_code=429, headers={}),
                body=None,
            ),
        ):
            with pytest.raises(ModelError):
                gw.call("hello", "v1", {"name": "Test"}, Greeting)
