"""Unit tests for Mode B citation verifier (B5 ACs 1–6)."""

from __future__ import annotations

import uuid
from datetime import date, datetime

import pytest

from src.gateway.citation_verifier_mode_b import verify
from src.gateway.errors import UnitMismatchError, UnmatchedNumericError
from src.persistence.models import BiomarkerRecordRow

_DATE = date(2025, 1, 15)


def _make_record(
    canonical_value: float | None,
    canonical_unit: str | None = "%",
    original_value: str = "0",
    original_unit: str | None = None,
) -> BiomarkerRecordRow:
    return BiomarkerRecordRow(
        record_id=uuid.uuid4(),
        patient_id=uuid.uuid4(),
        document_id=None,
        canonical_biomarker_id="hba1c",
        pending_taxonomy_id=None,
        original_name="HbA1c",
        original_value=original_value,
        original_unit=original_unit,
        original_range=None,
        canonical_value=canonical_value,
        canonical_unit=canonical_unit,
        collection_date=_DATE,
        lab_source="LabCorp",
        extraction_confidence=0.95,
        verified_by="auto",
        created_at=datetime(2025, 1, 16, 9, 0, 0),
    )


def _make_set(*records: BiomarkerRecordRow) -> dict[uuid.UUID, BiomarkerRecordRow]:
    return {r.record_id: r for r in records}


# ── AC1: valid prose matches ───────────────────────────────────────────────────


def test_valid_prose_passes() -> None:
    """AC1: prose with two known values both in retrieval set — passes."""
    r1 = _make_record(6.8, "%", "6.8")
    r2 = _make_record(7.1, "%", "7.1")
    prose = "Your HbA1c was 6.8%, down from 7.1%."
    verify(prose, _make_set(r1, r2))  # must not raise


def test_empty_prose_passes() -> None:
    verify("", {})  # trivially valid


def test_prose_with_no_numerics_passes() -> None:
    verify("HbA1c is trending upward.", {})  # no extractable numerics


# ── AC2: unmatched numeric ─────────────────────────────────────────────────────


def test_unmatched_numeric_raises() -> None:
    """AC2: value not in retrieval set → UnmatchedNumericError."""
    r = _make_record(6.8, "%", "6.8")
    with pytest.raises(UnmatchedNumericError):
        verify("HbA1c was 7.0%.", _make_set(r))


def test_empty_retrieval_set_raises() -> None:
    """Any numeric against an empty retrieval set must fail."""
    with pytest.raises(UnmatchedNumericError):
        verify("HbA1c was 6.8%.", {})


# ── AC3: unit matching ─────────────────────────────────────────────────────────


def test_unit_mismatch_raises() -> None:
    """AC3: value matches but unit doesn't → UnitMismatchError."""
    r = _make_record(6.8, "%", "6.8")  # canonical_unit = "%"
    with pytest.raises(UnitMismatchError):
        verify("HbA1c was 6.8 mmol/mol.", _make_set(r))


def test_no_unit_in_prose_skips_unit_check() -> None:
    """AC3: if prose has no unit, value-only match is sufficient."""
    r = _make_record(6.8, "%", "6.8")
    verify("HbA1c was 6.8.", _make_set(r))  # no unit in prose → must not raise


def test_unit_matched_via_original_unit() -> None:
    """AC3: unit matches original_unit when canonical_unit is None."""
    r = _make_record(6.8, None, "6.8", original_unit="%")
    verify("HbA1c was 6.8%.", _make_set(r))


# ── AC4: integer exact match ───────────────────────────────────────────────────


def test_integer_exact_match_passes() -> None:
    """AC4: integer value exactly matching stored → passes."""
    r = _make_record(120.0, "mg/dL", "120")
    verify("BP systolic 120 mg/dL.", _make_set(r))


def test_integer_off_by_one_raises() -> None:
    """AC4: integer 121 does not match stored 120 (no tolerance for integers)."""
    r = _make_record(120.0, "mg/dL", "120")
    with pytest.raises(UnmatchedNumericError):
        verify("BP systolic 121 mg/dL.", _make_set(r))


# ── AC5: decimal tolerance ─────────────────────────────────────────────────────


def test_decimal_within_tolerance_passes() -> None:
    """AC5: 6.834 is +0.49% above 6.8 — within ±0.5%."""
    r = _make_record(6.8, "%", "6.8")
    verify("HbA1c 6.834%.", _make_set(r))


def test_decimal_exceeds_tolerance_raises() -> None:
    """AC5: 6.841 is +0.60% above 6.8 — outside ±0.5%."""
    r = _make_record(6.8, "%", "6.8")
    with pytest.raises(UnmatchedNumericError):
        verify("HbA1c 6.841%.", _make_set(r))


def test_decimal_matches_original_value() -> None:
    """AC5: canonical_value=None, matches via original_value string."""
    r = _make_record(None, "%", original_value="6.8")
    verify("HbA1c 6.8%.", _make_set(r))


def test_zero_stored_exact_match_passes() -> None:
    """_within_tol special-cases stored==0.0 to avoid divide-by-zero; cited 0.0 must pass."""
    r = _make_record(0.0, "mmol/L", "0.0")
    verify("Glucose 0.0 mmol/L.", _make_set(r))


def test_zero_stored_nonzero_cited_raises() -> None:
    """Any non-zero value cited against a stored 0.0 must be rejected."""
    r = _make_record(0.0, "mmol/L", "0.0")
    with pytest.raises(UnmatchedNumericError):
        verify("Glucose 0.1 mmol/L.", _make_set(r))
