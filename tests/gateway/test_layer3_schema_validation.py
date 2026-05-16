"""Unit tests for Layer 3 schema validation (AC3, AC6)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel

from src.gateway.errors import SchemaValidationError
from src.gateway.guardrails.layer3_deterministic import Layer3


class Report(BaseModel):
    summary: str
    value: float


def _layer3_no_phrases(tmp_path: Path) -> Layer3:
    """Layer3 with empty phrase list so schema tests aren't contaminated."""
    shared = tmp_path / "_shared"
    shared.mkdir()
    (shared / "banned_phrases.txt").write_text("", encoding="utf-8")
    return Layer3(prompts_dir=tmp_path)


def test_valid_output_returns_model(tmp_path: Path) -> None:
    l3 = _layer3_no_phrases(tmp_path)
    result = l3.validate_output({"summary": "HbA1c stable", "value": 7.2}, Report)
    assert result.summary == "HbA1c stable"
    assert result.value == pytest.approx(7.2)


def test_missing_required_field_raises_schema_error(tmp_path: Path) -> None:
    l3 = _layer3_no_phrases(tmp_path)
    with pytest.raises(SchemaValidationError):
        l3.validate_output({"summary": "HbA1c stable"}, Report)  # missing value


def test_wrong_type_raises_schema_error(tmp_path: Path) -> None:
    l3 = _layer3_no_phrases(tmp_path)
    with pytest.raises(SchemaValidationError):
        l3.validate_output({"summary": 123, "value": 7.2}, Report)  # summary must be str


def test_field_errors_contains_loc(tmp_path: Path) -> None:
    l3 = _layer3_no_phrases(tmp_path)
    with pytest.raises(SchemaValidationError) as exc_info:
        l3.validate_output({"summary": "ok"}, Report)  # missing value
    errors = exc_info.value.field_errors
    assert len(errors) >= 1
    locs = [e["loc"] for e in errors]
    assert any("value" in loc for loc in locs)


def test_gateway_apply_output_validators_uses_layer3(prompts_dir: Path, tmp_path: Path) -> None:
    """Verify the gateway seam raises SchemaValidationError (not raw ValidationError)."""
    from src.gateway.gateway import Gateway

    gw = Gateway(prompts_dir=prompts_dir, api_key="test-key")
    # Point layer3 at empty phrase file so only schema is tested
    phrase_dir = tmp_path / "_shared"
    phrase_dir.mkdir()
    (phrase_dir / "banned_phrases.txt").write_text("", encoding="utf-8")
    gw._layer3 = Layer3(prompts_dir=tmp_path)

    with pytest.raises(SchemaValidationError):
        gw._apply_output_validators({"summary": "ok"}, Report)  # missing value
