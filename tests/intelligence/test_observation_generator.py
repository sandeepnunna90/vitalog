"""Unit tests for ObservationGenerator (F2 ACs 1–6)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.intelligence.observation_generator import _SAFE_REFUSAL, ObservationGenerator
from src.intelligence.observation_schemas import Observation
from src.intelligence.trend_engine import TrendEngine
from src.intelligence.trend_schemas import TrendBand, TrendResult
from src.persistence.biomarker_repository import BiomarkerRepository
from src.persistence.models import BiomarkerRecordRow

_PROJECT_ROOT = Path(__file__).parent.parent.parent
_PROMPTS_DIR = _PROJECT_ROOT / "prompts"
_PATIENT_ID = uuid.uuid4()
_RECORD_ID = uuid.uuid4()

_GOOD_RAW: dict[str, Any] = {
    "text": (
        "Your HbA1c on March 12, 2026 was 6.8%, which is below the ADA target of "
        "less than 7.0% for adults with diabetes (ADA Standards of Care 2024)."
    ),
    "citations": [
        {"kind": "record", "record_id": str(_RECORD_ID)},
        {"kind": "guideline", "source": "ADA", "range": "<7.0%"},
    ],
}

# Raw response that cites a value (9.9) absent from the retrieval set → Mode B rejects
_BAD_RAW: dict[str, Any] = {
    "text": "Your HbA1c was 9.9%, which is above the ADA target.",
    "citations": [{"kind": "record", "record_id": str(_RECORD_ID)}],
}


def _make_record(**kwargs: Any) -> BiomarkerRecordRow:
    defaults: dict[str, Any] = {
        "record_id": _RECORD_ID,
        "patient_id": _PATIENT_ID,
        "document_id": None,
        "canonical_biomarker_id": "hba1c",
        "pending_taxonomy_id": None,
        "original_name": "HbA1c",
        "original_value": "6.8",
        "original_unit": "%",
        "original_range": None,
        "canonical_value": 6.8,
        "canonical_unit": "%",
        "collection_date": date(2026, 3, 12),
        "lab_source": "Quest Diagnostics",
        "extraction_confidence": 98.0,
        "verified_by": "auto",
        "created_at": datetime(2026, 3, 12, 10, 0, 0),
    }
    defaults.update(kwargs)
    return BiomarkerRecordRow.model_validate(defaults)


def _make_band(
    label: str = "ADA target diabetes",
    lower: float | None = None,
    upper: float | None = 7.0,
    raw_range: str = "<7.0%",
    citation: str | None = "ADA Standards of Care 2024",
) -> TrendBand:
    return TrendBand(label=label, lower=lower, upper=upper, raw_range=raw_range, citation=citation)


def _make_trend(bands: list[TrendBand] | None = None) -> TrendResult:
    return TrendResult(
        patient_id=_PATIENT_ID,
        canonical_id="hba1c",
        canonical_unit="%",
        points=[],
        bands=bands if bands is not None else [_make_band()],
        pending_review_count=0,
    )


def _make_generator(
    record: BiomarkerRecordRow | None = None,
    trend: TrendResult | None = None,
    audit_repo: Any = None,
) -> ObservationGenerator:
    repo = MagicMock(spec=BiomarkerRepository)
    repo.get.return_value = record if record is not None else _make_record()

    engine = MagicMock(spec=TrendEngine)
    engine.get_trend.return_value = trend if trend is not None else _make_trend()

    from src.gateway.gateway import Gateway

    gw = Gateway(prompts_dir=_PROMPTS_DIR)
    return ObservationGenerator(
        gateway=gw,
        biomarker_repo=repo,
        trend_engine=engine,
        audit_repo=audit_repo,
    )


# ── AC1: happy path structure ─────────────────────────────────────────────────


def test_generate_returns_observation_structure() -> None:
    """AC1: generate() returns an Observation with correct field types."""
    gen = _make_generator()
    with patch(
        "src.gateway.anthropic_adapter.AnthropicAdapter.call",
        return_value=(_GOOD_RAW, 50, 20),
    ):
        obs = gen.generate(_RECORD_ID)

    assert isinstance(obs, Observation)
    assert obs.record_id == _RECORD_ID
    assert isinstance(obs.text, str)
    assert len(obs.text) > 0
    assert isinstance(obs.citations, list)


def test_generate_record_id_matches() -> None:
    """AC1: observation.record_id equals the record_id passed to generate()."""
    gen = _make_generator()
    with patch(
        "src.gateway.anthropic_adapter.AnthropicAdapter.call",
        return_value=(_GOOD_RAW, 50, 20),
    ):
        obs = gen.generate(_RECORD_ID)

    assert obs.record_id == _RECORD_ID


# ── AC6: prompt version ───────────────────────────────────────────────────────


def test_generate_prompt_version_is_v1() -> None:
    """AC6: prompt_version field must equal 'v1'."""
    gen = _make_generator()
    with patch(
        "src.gateway.anthropic_adapter.AnthropicAdapter.call",
        return_value=(_GOOD_RAW, 50, 20),
    ):
        obs = gen.generate(_RECORD_ID)

    assert obs.prompt_version == "v1"


# ── AC3: Mode B — guideline bounds in retrieval set ──────────────────────────


def test_generate_guideline_bound_passes_mode_b() -> None:
    """AC3: prose that cites the guideline bound value (7.0) must not be rejected."""
    gen = _make_generator(trend=_make_trend(bands=[_make_band(upper=7.0)]))
    # _GOOD_RAW contains "7.0" which maps to the guideline band upper bound
    with patch(
        "src.gateway.anthropic_adapter.AnthropicAdapter.call",
        return_value=(_GOOD_RAW, 50, 20),
    ):
        obs = gen.generate(_RECORD_ID)

    assert _SAFE_REFUSAL not in obs.text


# ── AC6: safe refusal on double Mode B failure ───────────────────────────────


def test_generate_safe_refusal_when_mode_b_fails_twice() -> None:
    """AC6: if both attempts return a Mode B-rejected value, return safe-refusal text."""
    gen = _make_generator()
    # 9.9 is not in the retrieval set (record has 6.8, band upper is 7.0)
    with patch(
        "src.gateway.anthropic_adapter.AnthropicAdapter.call",
        return_value=(_BAD_RAW, 50, 20),
    ):
        obs = gen.generate(_RECORD_ID)

    assert obs.text == _SAFE_REFUSAL
    assert obs.citations == []


def test_generate_retry_succeeds_on_second_attempt() -> None:
    """AC6: first attempt fails Mode B; second attempt returns valid output."""
    gen = _make_generator()
    call_count = 0

    def _side_effect(**_kwargs: Any) -> tuple[dict[str, Any], int, int]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return (_BAD_RAW, 50, 20)
        return (_GOOD_RAW, 50, 20)

    with patch(
        "src.gateway.anthropic_adapter.AnthropicAdapter.call",
        side_effect=_side_effect,
    ):
        obs = gen.generate(_RECORD_ID)

    assert obs.text != _SAFE_REFUSAL
    assert call_count == 2


# ── AC6: audit log ────────────────────────────────────────────────────────────


def test_generate_logs_audit_event() -> None:
    """AC6: audit_repo.record is called with event_type='observation_generated'."""
    audit_repo = MagicMock()
    gen = _make_generator(audit_repo=audit_repo)

    with patch(
        "src.gateway.anthropic_adapter.AnthropicAdapter.call",
        return_value=(_GOOD_RAW, 50, 20),
    ):
        gen.generate(_RECORD_ID)

    audit_repo.record.assert_called_once()
    call_kwargs = audit_repo.record.call_args
    assert call_kwargs.kwargs["event_type"] == "observation_generated"


# ── Edge: record not found ────────────────────────────────────────────────────


def test_generate_record_not_found_raises() -> None:
    """generate() raises ValueError when the record does not exist."""
    gen = _make_generator(record=None)
    gen._repo.get.return_value = None

    with pytest.raises(ValueError, match=str(_RECORD_ID)):
        with patch(
            "src.gateway.anthropic_adapter.AnthropicAdapter.call",
            return_value=(_GOOD_RAW, 50, 20),
        ):
            gen.generate(_RECORD_ID)
