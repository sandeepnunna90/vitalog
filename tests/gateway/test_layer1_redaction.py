"""Unit tests for Layer 1 PHI redaction (AC1, AC6)."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from src.gateway.guardrails.layer1 import redact_for_log

# ── Pure redaction unit tests ──────────────────────────────────────────────────


def test_email_redacted() -> None:
    result = redact_for_log({"text": "contact john@example.com for info"})
    assert "[PHI:EMAIL]" in result["text"]
    assert "john@example.com" not in result["text"]


def test_phone_redacted() -> None:
    result = redact_for_log({"phone": "555-123-4567"})
    assert "[PHI:PHONE]" in result["phone"]
    assert "555-123-4567" not in result["phone"]


def test_dob_iso_redacted() -> None:
    result = redact_for_log({"dob": "DOB: 1970-01-01"})
    assert "[PHI:DOB]" in result["dob"]
    assert "1970-01-01" not in result["dob"]


def test_dob_slash_redacted() -> None:
    result = redact_for_log({"dob": "born 01/15/1970"})
    assert "[PHI:DOB]" in result["dob"]
    assert "01/15/1970" not in result["dob"]


def test_mrn_redacted() -> None:
    result = redact_for_log({"note": "MRN: 12345 is in chart"})
    assert "[PHI:MRN]" in result["note"]
    assert "12345" not in result["note"]


def test_non_phi_unchanged() -> None:
    result = redact_for_log({"biomarker": "glucose", "value": "5.2"})
    assert result["biomarker"] == "glucose"
    assert result["value"] == "5.2"


def test_original_dict_not_mutated() -> None:
    original: dict[str, Any] = {"email": "test@clinic.com"}
    _ = redact_for_log(original)
    assert original["email"] == "test@clinic.com"


def test_nested_dict_redacted() -> None:
    result = redact_for_log({"patient": {"contact": "me@mail.com", "age": "42"}})
    nested = result["patient"]
    assert isinstance(nested, dict)
    assert "[PHI:EMAIL]" in nested["contact"]
    assert nested["age"] == "42"


def test_non_string_values_pass_through() -> None:
    result = redact_for_log({"count": 7, "flag": True})
    assert result["count"] == 7
    assert result["flag"] is True


# ── Integration: eval log written with redacted inputs ─────────────────────────


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


def test_eval_log_contains_redacted_values(prompts_dir: Path, tmp_path: Path) -> None:
    from src.gateway.eval_logger import EvalLogger
    from src.gateway.gateway import Gateway

    runs_dir = tmp_path / "runs"
    gw = Gateway(prompts_dir=prompts_dir, api_key="test-key")
    gw._logger = EvalLogger(runs_dir)

    from pydantic import BaseModel

    class Greeting(BaseModel):
        message: str

    with patch(
        "src.gateway.gateway.AnthropicAdapter.call",
        return_value=({"message": "Hi"}, 10, 5),
    ):
        gw.call("hello", "v1", {"name": "patient@clinic.com"}, Greeting)

    entries = list(runs_dir.rglob("*.jsonl"))
    assert len(entries) == 1
    data = json.loads(entries[0].read_text())

    # Original email must not appear in the log
    assert "patient@clinic.com" not in json.dumps(data["inputs_redacted"])
    # Redaction tag must appear
    assert "[PHI:EMAIL]" in json.dumps(data["inputs_redacted"])
