"""Mode A constraint tests for the Summary Generator (F5).

These tests use verify_mode_a directly — no gateway, no mocks of the verifier.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

import pytest

from src.gateway.citation_schemas import Citation
from src.gateway.citation_verifier_mode_a import verify as verify_mode_a
from src.gateway.errors import ModeAVerificationError, OwnershipLeakError
from src.persistence.models import BiomarkerRecordRow

_PATIENT_ID = uuid.uuid4()
_OTHER_PATIENT_ID = uuid.uuid4()
_RECORD_ID = uuid.uuid4()


def _make_record(
    record_id: uuid.UUID = _RECORD_ID,
    patient_id: uuid.UUID = _PATIENT_ID,
    canonical_value: float = 6.8,
    canonical_unit: str = "%",
    collection_date: date = date(2026, 3, 12),
) -> BiomarkerRecordRow:
    return BiomarkerRecordRow.model_validate(
        {
            "record_id": record_id,
            "patient_id": patient_id,
            "document_id": None,
            "canonical_biomarker_id": "hba1c",
            "pending_taxonomy_id": None,
            "original_name": "HbA1c",
            "original_value": str(canonical_value),
            "original_unit": canonical_unit,
            "original_range": None,
            "canonical_value": canonical_value,
            "canonical_unit": canonical_unit,
            "collection_date": collection_date,
            "lab_source": None,
            "extraction_confidence": None,
            "verified_by": "auto",
            "created_at": datetime(2026, 3, 12, 10, 0, 0),
        }
    )


def test_citation_outside_retrieval_set_rejected() -> None:
    """Citation with source_record_id absent from retrieval set raises ModeAVerificationError."""
    unknown_id = uuid.uuid4()
    citation = Citation(
        value=6.8,
        unit="%",
        collection_date=date(2026, 3, 12),
        source_record_id=unknown_id,
    )
    retrieval_set: dict[uuid.UUID, BiomarkerRecordRow] = {}  # empty — nothing in scope
    with pytest.raises(ModeAVerificationError):
        verify_mode_a([citation], _PATIENT_ID, retrieval_set)


def test_ownership_leak_rejected() -> None:
    """A citation pointing to a record from a different patient raises OwnershipLeakError."""
    other_record = _make_record(patient_id=_OTHER_PATIENT_ID)
    citation = Citation(
        value=6.8,
        unit="%",
        collection_date=date(2026, 3, 12),
        source_record_id=other_record.record_id,
    )
    retrieval_set = {other_record.record_id: other_record}
    with pytest.raises(OwnershipLeakError):
        verify_mode_a([citation], _PATIENT_ID, retrieval_set)


def test_unit_mismatch_rejected() -> None:
    """A citation with a mismatched unit raises ModeAVerificationError."""
    record = _make_record(canonical_unit="%")
    citation = Citation(
        value=6.8,
        unit="mmol/L",  # wrong unit
        collection_date=date(2026, 3, 12),
        source_record_id=record.record_id,
    )
    retrieval_set = {record.record_id: record}
    with pytest.raises(ModeAVerificationError):
        verify_mode_a([citation], _PATIENT_ID, retrieval_set)


def test_value_outside_tolerance_rejected() -> None:
    """A citation value more than 0.5% from the stored value raises ModeAVerificationError."""
    record = _make_record(canonical_value=6.8)
    # 6.8 * 1.006 = 6.8408 — just over the 0.5% tolerance; use literal to avoid IEEE 754 edge
    citation = Citation(
        value=7.034,  # >0.5% from 6.8 (3.44% diff)
        unit="%",
        collection_date=date(2026, 3, 12),
        source_record_id=record.record_id,
    )
    retrieval_set = {record.record_id: record}
    with pytest.raises(ModeAVerificationError):
        verify_mode_a([citation], _PATIENT_ID, retrieval_set)
