"""Unit tests for Layer 3 banned-phrase scanner (AC1, AC5)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel

from src.gateway.errors import BannedPhraseViolation, SchemaValidationError
from src.gateway.guardrails.layer3_deterministic import Layer3


class Report(BaseModel):
    summary: str


def _make_layer3(tmp_path: Path, phrases: list[str] | None = None) -> Layer3:
    """Build a Layer3 instance pointing at a temp _shared dir with custom phrases."""
    shared = tmp_path / "_shared"
    shared.mkdir(exist_ok=True)
    content = "\n".join(phrases) + "\n" if phrases else ""
    (shared / "banned_phrases.txt").write_text(content, encoding="utf-8")
    return Layer3(prompts_dir=tmp_path)


def test_phrase_detected(tmp_path: Path) -> None:
    l3 = _make_layer3(tmp_path, ["you should"])
    with pytest.raises(BannedPhraseViolation) as exc_info:
        l3.validate_output({"summary": "You should take more insulin."}, Report)
    assert any("you should" in p for p in exc_info.value.phrases)


def test_case_insensitive(tmp_path: Path) -> None:
    l3 = _make_layer3(tmp_path, ["you should"])
    with pytest.raises(BannedPhraseViolation):
        l3.validate_output({"summary": "YOU SHOULD ask your doctor."}, Report)


def test_word_boundary_whole_phrase_only(tmp_path: Path) -> None:
    l3 = _make_layer3(tmp_path, ["consider taking"])
    # "consider" alone must not trigger
    result = l3.validate_output({"summary": "You may consider the lab results."}, Report)
    assert result.summary == "You may consider the lab results."

    # full phrase must trigger
    with pytest.raises(BannedPhraseViolation):
        l3.validate_output({"summary": "You may consider taking aspirin."}, Report)


def test_clean_output_passes(tmp_path: Path) -> None:
    l3 = _make_layer3(tmp_path, ["you should"])
    result = l3.validate_output({"summary": "Your HbA1c is 7.2%."}, Report)
    assert result.summary == "Your HbA1c is 7.2%."


def test_multiple_phrases_all_returned(tmp_path: Path) -> None:
    l3 = _make_layer3(tmp_path, ["I recommend", "you need to"])
    with pytest.raises(BannedPhraseViolation) as exc_info:
        l3.validate_output({"summary": "I recommend testing and you need to act."}, Report)
    patterns = exc_info.value.phrases
    assert any("I recommend" in p for p in patterns)
    assert any("you need to" in p for p in patterns)


def test_schema_validated_before_banned_phrase(tmp_path: Path) -> None:
    l3 = _make_layer3(tmp_path, ["you should"])

    class Strict(BaseModel):
        count: int

    # schema fails → SchemaValidationError, not BannedPhraseViolation
    with pytest.raises(SchemaValidationError):
        l3.validate_output({"count": "you should take more"}, Strict)


def test_banned_phrases_file_has_sufficient_entries() -> None:
    phrases_path = (
        Path(__file__).parent.parent.parent / "prompts" / "_shared" / "banned_phrases.txt"
    )
    raw = phrases_path.read_text(encoding="utf-8").splitlines()
    lines = [ln.strip() for ln in raw if ln.strip()]
    assert len(lines) >= 20, f"Expected ≥20 banned phrases, found {len(lines)}"


def test_missing_phrases_file_does_not_raise(tmp_path: Path) -> None:
    # No _shared dir at all — Layer3 should degrade gracefully
    l3 = Layer3(prompts_dir=tmp_path)
    result = l3.validate_output({"summary": "you should do something"}, Report)
    assert "you should" in result.summary  # passes because phrase list is empty
