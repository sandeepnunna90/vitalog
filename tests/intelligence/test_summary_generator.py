"""Unit tests for SummaryGenerator (F5 ACs 1–7)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any
from unittest.mock import MagicMock, patch

from src.gateway.errors import BannedPhraseViolation, ModeAVerificationError, OutputValidationError
from src.intelligence.summary_generator import (
    DISCLAIMER,
    SummaryGenerator,
    _detect_data_gaps,
)
from src.intelligence.summary_schemas import Summary, SummaryOutput, SummaryOutputCitation
from src.persistence.models import BiomarkerRecordRow

_PATIENT_ID = uuid.UUID("7f3b1c5e-4d2a-4e8f-b6c9-1a2b3c4d5e6f")
_RECORD_ID_1 = uuid.uuid4()
_RECORD_ID_2 = uuid.uuid4()


def _make_record(
    record_id: uuid.UUID = _RECORD_ID_1,
    canonical_biomarker_id: str = "hba1c",
    original_name: str = "HbA1c",
    canonical_value: float = 6.8,
    canonical_unit: str = "%",
    collection_date: date = date(2026, 3, 12),
    verified_by: str = "auto",
) -> BiomarkerRecordRow:
    return BiomarkerRecordRow.model_validate(
        {
            "record_id": record_id,
            "patient_id": _PATIENT_ID,
            "document_id": None,
            "canonical_biomarker_id": canonical_biomarker_id,
            "pending_taxonomy_id": None,
            "original_name": original_name,
            "original_value": str(canonical_value),
            "original_unit": canonical_unit,
            "original_range": None,
            "canonical_value": canonical_value,
            "canonical_unit": canonical_unit,
            "collection_date": collection_date,
            "lab_source": "Quest Diagnostics",
            "extraction_confidence": 98.0,
            "verified_by": verified_by,
            "created_at": datetime(2026, 3, 12, 10, 0, 0),
        }
    )


def _good_output() -> SummaryOutput:
    return SummaryOutput(
        conditions_section="Type 2 Diabetes, Hypertension",
        medications_section="Metformin 1000mg",
        results_section="HbA1c: 6.8% (March 12, 2026)",
        trends_section="HbA1c decreased from 7.1% to 6.8% over 6 months.",
        data_gaps_section="postprandial_glucose",
        patient_notes="",
        citations=[
            SummaryOutputCitation(
                value=6.8,
                unit="%",
                collection_date="2026-03-12",
                source_record_id=str(_RECORD_ID_1),
            )
        ],
    )


def _make_generator(gateway: Any, repo: Any, audit_repo: Any = None) -> SummaryGenerator:
    return SummaryGenerator(gateway=gateway, biomarker_repo=repo, audit_repo=audit_repo)


def _mock_repo(records: list[BiomarkerRecordRow]) -> MagicMock:
    repo = MagicMock()
    repo.list_for_patient.return_value = records
    return repo


@patch("src.intelligence.summary_generator.load_patient_profile")
@patch("src.intelligence.summary_generator.verify_mode_a")
def test_happy_path(mock_verify: MagicMock, mock_profile: MagicMock) -> None:
    """Valid SummaryOutput → Summary built with disclaimer and citation_count."""
    mock_profile.return_value = MagicMock(
        conditions=["T2D"],
        medications=[MagicMock(name="Metformin", dose="1000mg")],
        allergies=[],
    )
    record = _make_record()
    repo = _mock_repo([record])
    gateway = MagicMock()
    gateway.call.return_value = _good_output()

    gen = _make_generator(gateway, repo)
    summary = gen.generate(_PATIENT_ID)

    assert isinstance(summary, Summary)
    assert summary.is_fallback is False
    assert summary.disclaimer == DISCLAIMER
    assert summary.citation_count == 1
    assert summary.prompt_version == "v2"
    assert summary.conditions_section == "Type 2 Diabetes, Hypertension"
    mock_verify.assert_called_once()


@patch("src.intelligence.summary_generator.load_patient_profile")
@patch("src.intelligence.summary_generator.verify_mode_a")
def test_disclaimer_always_present(mock_verify: MagicMock, mock_profile: MagicMock) -> None:
    """Disclaimer is verbatim even when is_fallback=True."""
    mock_profile.return_value = MagicMock(conditions=[], medications=[], allergies=[])
    repo = _mock_repo([])
    gateway = MagicMock()
    gateway.call.side_effect = OutputValidationError("bad output")

    gen = _make_generator(gateway, repo)
    summary = gen.generate(_PATIENT_ID)

    assert summary.is_fallback is True
    assert summary.disclaimer == DISCLAIMER


def test_disclaimer_not_in_llm_schema() -> None:
    """SummaryOutput (LLM schema) must not have a disclaimer field."""
    fields = set(SummaryOutput.model_fields.keys())
    assert "disclaimer" not in fields


@patch("src.intelligence.summary_generator.load_patient_profile")
@patch("src.intelligence.summary_generator.verify_mode_a")
def test_retry_on_banned_phrase(mock_verify: MagicMock, mock_profile: MagicMock) -> None:
    """First attempt raises BannedPhraseViolation; second succeeds → not fallback."""
    mock_profile.return_value = MagicMock(
        conditions=["T2D"],
        medications=[],
        allergies=[],
    )
    record = _make_record()
    repo = _mock_repo([record])
    gateway = MagicMock()
    good = _good_output()
    gateway.call.side_effect = [BannedPhraseViolation(["you should"]), good]

    gen = _make_generator(gateway, repo)
    summary = gen.generate(_PATIENT_ID)

    assert summary.is_fallback is False
    assert gateway.call.call_count == 2


@patch("src.intelligence.summary_generator.load_patient_profile")
@patch("src.intelligence.summary_generator.verify_mode_a")
def test_safe_refusal_on_double_failure(mock_verify: MagicMock, mock_profile: MagicMock) -> None:
    """Both attempts fail → is_fallback=True with empty sections and disclaimer."""
    mock_profile.return_value = MagicMock(conditions=[], medications=[], allergies=[])
    repo = _mock_repo([])
    gateway = MagicMock()
    gateway.call.side_effect = OutputValidationError("bad")

    gen = _make_generator(gateway, repo)
    summary = gen.generate(_PATIENT_ID)

    assert summary.is_fallback is True
    assert summary.conditions_section == ""
    assert summary.citations == []
    assert summary.disclaimer == DISCLAIMER
    assert gateway.call.call_count == 2


@patch("src.intelligence.summary_generator.load_patient_profile")
@patch("src.intelligence.summary_generator.verify_mode_a")
def test_mode_a_rejection_triggers_retry(mock_verify: MagicMock, mock_profile: MagicMock) -> None:
    """ModeAVerificationError on first attempt → second attempt is made."""
    mock_profile.return_value = MagicMock(
        conditions=["T2D"],
        medications=[],
        allergies=[],
    )
    record = _make_record()
    repo = _mock_repo([record])
    gateway = MagicMock()
    good = _good_output()
    gateway.call.return_value = good
    from src.gateway.citation_schemas import Citation

    bad_citation = Citation(
        value=6.8,
        unit="mmol/L",
        collection_date=date(2026, 3, 12),
        source_record_id=_RECORD_ID_1,
    )
    mock_verify.side_effect = [
        ModeAVerificationError("unit mismatch", bad_citation),
        None,
    ]

    gen = _make_generator(gateway, repo)
    summary = gen.generate(_PATIENT_ID)

    assert summary.is_fallback is False
    assert gateway.call.call_count == 2


@patch("src.intelligence.summary_generator.load_biomarker_groups")
def test_data_gaps_detection(mock_groups: MagicMock) -> None:
    """_detect_data_gaps returns canonical names for condition biomarkers with no records."""
    mock_groups.return_value = {
        "conditions": {
            "T2D": {
                "display_name": "Type 2 Diabetes",
                "biomarkers": ["hba1c", "fasting_glucose", "egfr"],
            }
        }
    }
    records = [_make_record(canonical_biomarker_id="hba1c")]
    gaps = _detect_data_gaps(["T2D"], records)
    # hba1c is recorded; fasting_glucose and egfr are gaps
    assert len(gaps) == 2


@patch("src.intelligence.summary_generator.load_biomarker_groups")
def test_data_gaps_unknown_condition_code_skipped(mock_groups: MagicMock) -> None:
    """Unknown condition code in profile is silently skipped (no KeyError) and emits a warning."""
    mock_groups.return_value = {"conditions": {"T2D": {"biomarkers": ["hba1c"]}}}
    import logging

    with patch.object(logging.getLogger("audit"), "warning") as mock_warn:
        gaps = _detect_data_gaps(["T2D", "UNKNOWN_COND"], [])
    # UNKNOWN_COND is not in biomarker_groups — warning emitted, no crash
    assert mock_warn.call_count >= 1
    # T2D gap still detected
    assert len(gaps) == 1


@patch("src.intelligence.summary_generator.load_patient_profile")
@patch("src.intelligence.summary_generator.verify_mode_a")
def test_audit_logged(mock_verify: MagicMock, mock_profile: MagicMock) -> None:
    """audit_repo.record is called with event_type='summary_generated'."""
    mock_profile.return_value = MagicMock(
        conditions=["T2D"],
        medications=[],
        allergies=[],
    )
    record = _make_record()
    repo = _mock_repo([record])
    gateway = MagicMock()
    gateway.call.return_value = _good_output()
    audit_repo = MagicMock()

    gen = _make_generator(gateway, repo, audit_repo=audit_repo)
    gen.generate(_PATIENT_ID)

    audit_repo.record.assert_called_once()
    call_kwargs = audit_repo.record.call_args.kwargs
    assert call_kwargs["event_type"] == "summary_generated"
