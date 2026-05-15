"""Unit tests for Layer 2 preamble, few-shot refusals, and schema enforcement retry (AC3–6)."""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.gateway.guardrails.layer2 import Layer2

# ── Layer2 unit tests ─────────────────────────────────────────────────────────


def test_preamble_prepended(tmp_path: Path) -> None:
    shared = tmp_path / "_shared"
    shared.mkdir()
    (shared / "safety_preamble.md").write_text("SAFETY PREAMBLE", encoding="utf-8")
    (shared / "few_shot_refusals").mkdir()

    l2 = Layer2(prompts_dir=tmp_path)
    result = l2.augment_system("original system prompt")

    assert result.startswith("SAFETY PREAMBLE")
    assert "original system prompt" in result


def test_preamble_before_original_system(tmp_path: Path) -> None:
    shared = tmp_path / "_shared"
    shared.mkdir()
    (shared / "safety_preamble.md").write_text("PREAMBLE TEXT", encoding="utf-8")
    (shared / "few_shot_refusals").mkdir()

    l2 = Layer2(prompts_dir=tmp_path)
    result = l2.augment_system("ORIGINAL")

    preamble_pos = result.index("PREAMBLE TEXT")
    original_pos = result.index("ORIGINAL")
    assert preamble_pos < original_pos


def test_injection_warning_prepended_before_preamble(tmp_path: Path) -> None:
    shared = tmp_path / "_shared"
    shared.mkdir()
    (shared / "safety_preamble.md").write_text("PREAMBLE", encoding="utf-8")
    (shared / "few_shot_refusals").mkdir()

    l2 = Layer2(prompts_dir=tmp_path)
    result = l2.augment_system("system", injection_warning="INJECTION WARNING")

    assert result.startswith("INJECTION WARNING")
    assert result.index("INJECTION WARNING") < result.index("PREAMBLE")


def test_missing_shared_dir_does_not_raise(tmp_path: Path) -> None:
    # No _shared dir at all — should gracefully return system unchanged
    l2 = Layer2(prompts_dir=tmp_path)
    result = l2.augment_system("my system")
    assert "my system" in result


# ── Refusal files count ───────────────────────────────────────────────────────


def test_at_least_3_refusal_files() -> None:
    refusals_dir = Path(__file__).parent.parent.parent / "prompts" / "_shared" / "few_shot_refusals"
    files = list(refusals_dir.glob("*.md"))
    assert len(files) >= 3, f"Expected ≥3 refusal files, found {len(files)}: {files}"


def test_refusals_included_in_system(tmp_path: Path) -> None:
    shared = tmp_path / "_shared"
    shared.mkdir()
    (shared / "safety_preamble.md").write_text("PREAMBLE", encoding="utf-8")
    refusals = shared / "few_shot_refusals"
    refusals.mkdir()
    (refusals / "r1.md").write_text("Q: question1\nA: answer1", encoding="utf-8")
    (refusals / "r2.md").write_text("Q: question2\nA: answer2", encoding="utf-8")
    (refusals / "r3.md").write_text("Q: question3\nA: answer3", encoding="utf-8")

    l2 = Layer2(prompts_dir=tmp_path)
    result = l2.augment_system("system")

    assert "question1" in result
    assert "question2" in result
    assert "question3" in result


# ── Gateway integration: preamble in system passed to adapter ─────────────────


@pytest.fixture()
def prompts_dir(tmp_path: Path) -> Path:
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
            ---
        """),
        encoding="utf-8",
    )
    return tmp_path


def test_gateway_call_system_contains_preamble(prompts_dir: Path) -> None:
    from pydantic import BaseModel

    from src.gateway.gateway import Gateway
    from src.gateway.guardrails.layer2 import Layer2

    class Greeting(BaseModel):
        message: str

    captured: dict[str, Any] = {}

    def _fake_call(**kwargs: Any) -> tuple[dict[str, Any], int, int]:
        captured["system"] = kwargs.get("system", "")
        return ({"message": "Hi"}, 10, 5)

    gw = Gateway(prompts_dir=prompts_dir, api_key="test-key")
    # Point Layer2 at the real prompts/_shared/ so the preamble is loaded
    real_prompts = Path(__file__).parent.parent.parent / "prompts"
    gw._layer2 = Layer2(real_prompts)
    with patch.object(gw._adapter, "call", side_effect=_fake_call):
        gw.call("hello", "v1", {"name": "Test"}, Greeting)

    # Verify a distinctive phrase from the real safety_preamble.md appears in system
    assert "Vitalog" in captured["system"] or "medical" in captured["system"].lower()


# ── Schema enforcement retry ──────────────────────────────────────────────────


def _make_tool_response(tool_name: str, tool_input: dict[str, Any]) -> MagicMock:
    block = MagicMock()
    block.type = "tool_use"
    block.input = tool_input
    response = MagicMock()
    response.content = [block]
    response.stop_reason = "tool_use"
    response.usage.input_tokens = 10
    response.usage.output_tokens = 5
    return response


def _make_empty_response() -> MagicMock:
    response = MagicMock()
    response.content = []
    response.stop_reason = "end_turn"
    return response


def test_schema_enforcement_retry_succeeds(prompts_dir: Path) -> None:
    """Adapter retries once with tightened prompt when no tool_use block returned."""
    from pydantic import BaseModel

    from src.gateway.gateway import Gateway

    class Greeting(BaseModel):
        message: str

    call_count = 0

    def _flaky(*args: Any, **kwargs: Any) -> MagicMock:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _make_empty_response()  # no tool_use block
        return _make_tool_response("Greeting", {"message": "Hello!"})

    gw = Gateway(prompts_dir=prompts_dir, api_key="test-key")
    with patch.object(gw._adapter._client.messages, "create", side_effect=_flaky):
        result = gw.call("hello", "v1", {"name": "Test"}, Greeting)

    assert result.message == "Hello!"
    assert call_count == 2


def test_schema_enforcement_retry_exhausted_raises(prompts_dir: Path) -> None:
    """After schema enforcement retry also fails, ModelError is raised."""
    from pydantic import BaseModel

    from src.gateway.errors import ModelError
    from src.gateway.gateway import Gateway

    class Greeting(BaseModel):
        message: str

    gw = Gateway(prompts_dir=prompts_dir, api_key="test-key")
    with patch.object(
        gw._adapter._client.messages,
        "create",
        return_value=_make_empty_response(),
    ):
        with pytest.raises(ModelError):
            gw.call("hello", "v1", {"name": "Test"}, Greeting)
