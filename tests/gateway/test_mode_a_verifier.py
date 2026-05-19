"""Unit tests for Mode A citation verifier (B4 ACs 1–4)."""

from __future__ import annotations

import uuid
from datetime import date, datetime

import pytest

from src.gateway.citation_schemas import Citation
from src.gateway.citation_verifier_mode_a import verify
from src.gateway.errors import ModeAVerificationError, OwnershipLeakError
from src.persistence.models import BiomarkerRecordRow

_DATE = date(2025, 1, 15)
_UNIT = "%"


def _make_record(
    patient_id: uuid.UUID,
    value: float | None,
    unit: str | None = _UNIT,
    collection_date: date | None = _DATE,
) -> BiomarkerRecordRow:
    return BiomarkerRecordRow(
        record_id=uuid.uuid4(),
        patient_id=patient_id,
        document_id=None,
        canonical_biomarker_id="hba1c",
        pending_taxonomy_id=None,
        original_name="HbA1c",
        original_value=str(value) if value is not None else "0",
        original_unit=unit,
        original_range=None,
        canonical_value=value,
        canonical_unit=unit,
        collection_date=collection_date,
        lab_source="LabCorp",
        extraction_confidence=0.95,
        verified_by="auto",
        created_at=datetime(2025, 1, 16, 9, 0, 0),
    )


def _make_citation(
    value: float,
    unit: str = _UNIT,
    collection_date: date = _DATE,
    record_id: uuid.UUID | None = None,
) -> Citation:
    return Citation(
        value=value,
        unit=unit,
        collection_date=collection_date,
        source_record_id=record_id or uuid.uuid4(),
    )


def _make_set(*records: BiomarkerRecordRow) -> dict[uuid.UUID, BiomarkerRecordRow]:
    return {r.record_id: r for r in records}


# ── AC1: happy-path verification ───────────────────────────────────────────────


def test_valid_single_citation_passes() -> None:
    patient_id = uuid.uuid4()
    record = _make_record(patient_id, 7.0)
    citation = _make_citation(7.0, record_id=record.record_id)
    verify([citation], patient_id, _make_set(record))  # must not raise


def test_valid_within_tolerance_passes() -> None:
    """Value at +0.49% (inside ±0.5% tolerance) must pass."""
    patient_id = uuid.uuid4()
    stored = 7.0
    cited = 7.034  # +0.486%, clearly inside tolerance; avoids FP boundary instability
    record = _make_record(patient_id, stored)
    citation = _make_citation(cited, record_id=record.record_id)
    verify([citation], patient_id, _make_set(record))


def test_valid_below_tolerance_passes() -> None:
    """Value at -0.4% (inside ±0.5% tolerance) must pass."""
    patient_id = uuid.uuid4()
    stored = 7.0
    cited = 6.972  # -0.4% below stored, clearly inside tolerance
    record = _make_record(patient_id, stored)
    citation = _make_citation(cited, record_id=record.record_id)
    verify([citation], patient_id, _make_set(record))


def test_empty_citations_passes() -> None:
    patient_id = uuid.uuid4()
    verify([], patient_id, {})  # trivially valid


def test_valid_multiple_citations_passes() -> None:
    patient_id = uuid.uuid4()
    r1 = _make_record(patient_id, 7.0, collection_date=date(2025, 1, 1))
    r2 = _make_record(patient_id, 7.2, collection_date=date(2025, 4, 1))
    r3 = _make_record(patient_id, 6.8, collection_date=date(2025, 7, 1))
    citations = [
        _make_citation(7.0, collection_date=date(2025, 1, 1), record_id=r1.record_id),
        _make_citation(7.2, collection_date=date(2025, 4, 1), record_id=r2.record_id),
        _make_citation(6.8, collection_date=date(2025, 7, 1), record_id=r3.record_id),
    ]
    verify(citations, patient_id, _make_set(r1, r2, r3))


# ── AC2: retrieval-set check ───────────────────────────────────────────────────


def test_record_not_in_retrieval_set_raises() -> None:
    patient_id = uuid.uuid4()
    citation = _make_citation(7.0)  # random record_id not in retrieval set
    with pytest.raises(ModeAVerificationError, match="not in retrieval set"):
        verify([citation], patient_id, {})


def test_record_not_in_retrieval_set_logs_security(caplog: pytest.LogCaptureFixture) -> None:
    patient_id = uuid.uuid4()
    citation = _make_citation(7.0)
    with caplog.at_level("ERROR", logger="verification.security"):
        with pytest.raises(ModeAVerificationError):
            verify([citation], patient_id, {})
    assert any("not in retrieval set" in r.message for r in caplog.records)


# ── AC3: numeric tolerance ─────────────────────────────────────────────────────


def test_value_exceeds_tolerance_raises() -> None:
    """0.6% difference must be rejected."""
    patient_id = uuid.uuid4()
    stored = 7.0
    cited = stored * 1.006  # 0.6% above stored
    record = _make_record(patient_id, stored)
    citation = _make_citation(cited, record_id=record.record_id)
    with pytest.raises(ModeAVerificationError, match="differs from stored"):
        verify([citation], patient_id, _make_set(record))


# ── AC4: ownership check ───────────────────────────────────────────────────────


def test_ownership_leak_raises_ownership_error() -> None:
    real_patient = uuid.uuid4()
    other_patient = uuid.uuid4()
    record = _make_record(other_patient, 7.0)  # belongs to other_patient
    citation = _make_citation(7.0, record_id=record.record_id)
    with pytest.raises(OwnershipLeakError):
        verify([citation], real_patient, _make_set(record))


def test_ownership_leak_logs_security(caplog: pytest.LogCaptureFixture) -> None:
    real_patient = uuid.uuid4()
    other_patient = uuid.uuid4()
    record = _make_record(other_patient, 7.0)
    citation = _make_citation(7.0, record_id=record.record_id)
    with caplog.at_level("ERROR", logger="verification.security"):
        with pytest.raises(OwnershipLeakError):
            verify([citation], real_patient, _make_set(record))
    assert any("ownership leak" in r.message for r in caplog.records)


# ── AC1: field-level matches ───────────────────────────────────────────────────


def test_unit_mismatch_raises() -> None:
    patient_id = uuid.uuid4()
    record = _make_record(patient_id, 7.0, unit="%")
    citation = _make_citation(7.0, unit="mmol/mol", record_id=record.record_id)
    with pytest.raises(ModeAVerificationError, match="unit mismatch"):
        verify([citation], patient_id, _make_set(record))


def test_unit_trailing_space_passes() -> None:
    """LLM-emitted unit with trailing space must not discard the whole summary."""
    patient_id = uuid.uuid4()
    record = _make_record(patient_id, 7.0, unit="mg/dL")
    citation = _make_citation(7.0, unit="mg/dL ", record_id=record.record_id)
    verify([citation], patient_id, _make_set(record))  # must not raise


def test_unit_leading_space_passes() -> None:
    """Unit with leading space must be accepted."""
    patient_id = uuid.uuid4()
    record = _make_record(patient_id, 7.0, unit="mg/dL")
    citation = _make_citation(7.0, unit=" mg/dL", record_id=record.record_id)
    verify([citation], patient_id, _make_set(record))  # must not raise


def test_date_mismatch_raises() -> None:
    patient_id = uuid.uuid4()
    record = _make_record(patient_id, 7.0, collection_date=date(2025, 1, 15))
    citation = _make_citation(7.0, collection_date=date(2025, 3, 1), record_id=record.record_id)
    with pytest.raises(ModeAVerificationError, match="collection_date mismatch"):
        verify([citation], patient_id, _make_set(record))
