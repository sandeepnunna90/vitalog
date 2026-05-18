"""Unit tests for the NLQ retrieval resolver (F3)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from unittest.mock import MagicMock

from src.intelligence.retrieval import ResolveResult, canonical_name, resolve_query
from src.persistence.biomarker_repository import BiomarkerRepository
from src.persistence.models import BiomarkerRecordRow

_PATIENT_ID = uuid.uuid4()


def _make_record(
    canonical_id: str = "hba1c",
    canonical_value: float = 6.8,
    canonical_unit: str = "%",
) -> BiomarkerRecordRow:
    return BiomarkerRecordRow.model_validate(
        {
            "record_id": uuid.uuid4(),
            "patient_id": _PATIENT_ID,
            "document_id": None,
            "canonical_biomarker_id": canonical_id,
            "pending_taxonomy_id": None,
            "original_name": "HbA1c",
            "original_value": str(canonical_value),
            "original_unit": canonical_unit,
            "original_range": None,
            "canonical_value": canonical_value,
            "canonical_unit": canonical_unit,
            "collection_date": date(2026, 3, 12),
            "lab_source": "Quest Diagnostics",
            "extraction_confidence": 98.0,
            "verified_by": "auto",
            "created_at": datetime(2026, 3, 12, 10, 0, 0),
        }
    )


def _make_repo(records: list[BiomarkerRecordRow]) -> BiomarkerRepository:
    repo = MagicMock(spec=BiomarkerRepository)
    repo.find_by_canonical_id.return_value = records
    return repo


# ── Direct alias matching ─────────────────────────────────────────────────────


def test_resolve_direct_biomarker_name() -> None:
    """Direct biomarker alias in query → record appears in retrieval_set."""
    repo = _make_repo([_make_record()])
    result = resolve_query("what's my HbA1c?", _PATIENT_ID, repo)

    assert isinstance(result, ResolveResult)
    assert len(result.retrieval_set) == 1
    assert result.missing_canonical_ids == []


def test_resolve_alias_case_insensitive() -> None:
    """Multi-word alias in any case is matched."""
    repo = _make_repo([_make_record()])
    result = resolve_query("show me my hemoglobin a1c results", _PATIENT_ID, repo)

    assert len(result.retrieval_set) == 1


def test_resolve_missing_biomarker_no_records() -> None:
    """Recognized alias but repo returns [] → canonical_id in missing list."""
    repo = _make_repo([])
    result = resolve_query("what's my HbA1c?", _PATIENT_ID, repo)

    assert result.retrieval_set == {}
    assert "hba1c" in result.missing_canonical_ids


# ── Condition keyword expansion ───────────────────────────────────────────────


def test_resolve_condition_keyword_diabetes() -> None:
    """'diabetes' in query → T2D biomarkers fetched from repo."""
    repo = _make_repo([_make_record()])
    result = resolve_query("show me my diabetes markers", _PATIENT_ID, repo)

    # repo.find_by_canonical_id called for multiple T2D biomarkers
    assert repo.find_by_canonical_id.call_count >= 1
    # At least one record (hba1c) should appear
    assert len(result.retrieval_set) >= 1


def test_resolve_condition_display_name_match() -> None:
    """Full condition display name 'type 2 diabetes' expands biomarkers."""
    repo = _make_repo([_make_record()])
    resolve_query("my type 2 diabetes results", _PATIENT_ID, repo)

    assert repo.find_by_canonical_id.call_count >= 1


# ── Unrecognized queries ──────────────────────────────────────────────────────


def test_resolve_unrecognized_query_empty() -> None:
    """Query with no recognized biomarker or condition → both returns empty."""
    repo = _make_repo([])
    result = resolve_query("what is the weather today?", _PATIENT_ID, repo)

    assert result.retrieval_set == {}
    assert result.missing_canonical_ids == []
    repo.find_by_canonical_id.assert_not_called()


# ── canonical_name helper ─────────────────────────────────────────────────────


def test_canonical_name_lookup() -> None:
    """canonical_name returns human-readable name from taxonomy."""
    assert canonical_name("hba1c") == "Hemoglobin A1c"


def test_canonical_name_unknown_returns_id() -> None:
    """canonical_name falls back to vitalog_id for unknown entries."""
    assert canonical_name("unknown_biomarker_xyz") == "unknown_biomarker_xyz"
