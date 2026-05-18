"""Unit tests for E4 — DuplicateDetector."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from unittest.mock import MagicMock

from src.normalization.constants import MODE_B_NUMERIC_TOLERANCE
from src.normalization.duplicate_detector import DuplicateDetector
from src.persistence.models import BiomarkerRecordRow

_PATIENT_ID = uuid.uuid4()
_CANONICAL_ID = "hba1c"
_COLLECTION_DATE = date(2026, 3, 12)


def _make_row(**kwargs: object) -> BiomarkerRecordRow:
    defaults: dict[str, object] = {
        "record_id": uuid.uuid4(),
        "patient_id": _PATIENT_ID,
        "document_id": None,
        "canonical_biomarker_id": _CANONICAL_ID,
        "pending_taxonomy_id": None,
        "original_name": "HbA1c",
        "original_value": "6.8",
        "original_unit": "%",
        "original_range": None,
        "canonical_value": 6.8,
        "canonical_unit": "%",
        "collection_date": _COLLECTION_DATE,
        "lab_source": "Quest Diagnostics",
        "extraction_confidence": 98.0,
        "verified_by": "auto",
        "created_at": datetime(2026, 3, 12, 10, 0, 0),
    }
    defaults.update(kwargs)
    return BiomarkerRecordRow.model_validate(defaults)


def _make_detector(prior_rows: list[BiomarkerRecordRow]) -> tuple[DuplicateDetector, MagicMock]:
    biomarker_repo = MagicMock()
    biomarker_repo.find_potential_duplicates.return_value = prior_rows
    audit_repo = MagicMock()
    detector = DuplicateDetector(biomarker_repo=biomarker_repo, audit_repo=audit_repo)
    return detector, audit_repo


# ── Duplicate scenarios ───────────────────────────────────────────────────────


def test_exact_duplicate_within_tolerance() -> None:
    prior = _make_row(record_id=uuid.uuid4(), canonical_value=6.8)
    detector, _ = _make_detector([prior])
    result = detector.check(_PATIENT_ID, _CANONICAL_ID, _COLLECTION_DATE, 6.8, uuid.uuid4())
    assert result.status == "duplicate"
    assert result.prior_record_id == prior.record_id
    assert result.notification_message is not None


def test_value_at_exactly_zero_point_five_pct_is_duplicate() -> None:
    ref = 6.8
    new_val = ref * (1 + MODE_B_NUMERIC_TOLERANCE)  # exactly at boundary
    prior = _make_row(canonical_value=ref)
    detector, _ = _make_detector([prior])
    result = detector.check(_PATIENT_ID, _CANONICAL_ID, _COLLECTION_DATE, new_val, uuid.uuid4())
    assert result.status == "duplicate"


def test_value_just_over_tolerance_is_conflict() -> None:
    ref = 6.8
    new_val = ref * (1 + MODE_B_NUMERIC_TOLERANCE + 1e-9)
    prior = _make_row(canonical_value=ref)
    detector, _ = _make_detector([prior])
    result = detector.check(_PATIENT_ID, _CANONICAL_ID, _COLLECTION_DATE, new_val, uuid.uuid4())
    assert result.status == "value_conflict"


def test_value_conflict_no_notification_message() -> None:
    prior = _make_row(canonical_value=6.8)
    detector, _ = _make_detector([prior])
    result = detector.check(_PATIENT_ID, _CANONICAL_ID, _COLLECTION_DATE, 9.0, uuid.uuid4())
    assert result.status == "value_conflict"
    assert result.notification_message is None


# ── Skip / no-match scenarios ─────────────────────────────────────────────────


def test_missing_date_returns_skipped_no_repo_call() -> None:
    biomarker_repo = MagicMock()
    audit_repo = MagicMock()
    detector = DuplicateDetector(biomarker_repo=biomarker_repo, audit_repo=audit_repo)
    result = detector.check(_PATIENT_ID, _CANONICAL_ID, None, 6.8, uuid.uuid4())
    assert result.status == "skipped_no_date"
    biomarker_repo.find_potential_duplicates.assert_not_called()


def test_audit_event_on_skipped_no_date() -> None:
    biomarker_repo = MagicMock()
    audit_repo = MagicMock()
    detector = DuplicateDetector(biomarker_repo=biomarker_repo, audit_repo=audit_repo)
    new_id = uuid.uuid4()
    detector.check(_PATIENT_ID, _CANONICAL_ID, None, 6.8, new_id)
    audit_repo.record.assert_called_once()
    call_kwargs = audit_repo.record.call_args.kwargs
    assert call_kwargs["event_type"] == "dedup_skipped_no_date"
    assert call_kwargs["payload"]["new_record_id"] == str(new_id)


def test_no_existing_records_returns_no_match() -> None:
    detector, audit_repo = _make_detector([])
    result = detector.check(_PATIENT_ID, _CANONICAL_ID, _COLLECTION_DATE, 6.8, uuid.uuid4())
    assert result.status == "no_match"
    audit_repo.record.assert_not_called()


def test_duplicate_wins_over_earlier_conflict() -> None:
    # prior[0] is a value_conflict; prior[1] is an exact duplicate.
    # The loop must not short-circuit on the conflict — duplicate takes priority.
    conflict_prior = _make_row(canonical_value=9.0)
    dup_prior = _make_row(canonical_value=6.8)
    detector, _ = _make_detector([conflict_prior, dup_prior])
    result = detector.check(_PATIENT_ID, _CANONICAL_ID, _COLLECTION_DATE, 6.8, uuid.uuid4())
    assert result.status == "duplicate"
    assert result.prior_record_id == dup_prior.record_id


def test_self_record_excluded() -> None:
    new_id = uuid.uuid4()
    prior = _make_row(record_id=new_id, canonical_value=6.8)
    detector, _ = _make_detector([prior])
    result = detector.check(_PATIENT_ID, _CANONICAL_ID, _COLLECTION_DATE, 6.8, new_id)
    assert result.status == "no_match"


def test_prior_with_none_canonical_value_skipped() -> None:
    prior = _make_row(canonical_value=None)
    detector, _ = _make_detector([prior])
    result = detector.check(_PATIENT_ID, _CANONICAL_ID, _COLLECTION_DATE, 6.8, uuid.uuid4())
    assert result.status == "no_match"


# ── Notification message formatting ──────────────────────────────────────────


def test_notification_message_includes_lab_source() -> None:
    prior = _make_row(canonical_value=6.8, lab_source="Quest Diagnostics")
    detector, _ = _make_detector([prior])
    result = detector.check(_PATIENT_ID, _CANONICAL_ID, _COLLECTION_DATE, 6.8, uuid.uuid4())
    assert result.notification_message is not None
    assert "Quest Diagnostics" in result.notification_message
    assert "March 12" in result.notification_message


def test_notification_message_without_lab_source() -> None:
    prior = _make_row(canonical_value=6.8, lab_source=None)
    detector, _ = _make_detector([prior])
    result = detector.check(_PATIENT_ID, _CANONICAL_ID, _COLLECTION_DATE, 6.8, uuid.uuid4())
    assert result.notification_message is not None
    assert "March 12" in result.notification_message
    assert "None" not in result.notification_message


# ── Audit events ──────────────────────────────────────────────────────────────


def test_audit_event_on_duplicate() -> None:
    prior = _make_row(canonical_value=6.8)
    detector, audit_repo = _make_detector([prior])
    new_id = uuid.uuid4()
    detector.check(_PATIENT_ID, _CANONICAL_ID, _COLLECTION_DATE, 6.8, new_id)
    audit_repo.record.assert_called_once()
    call_kwargs = audit_repo.record.call_args.kwargs
    assert call_kwargs["event_type"] == "duplicate_detected"
    assert call_kwargs["payload"]["new_record_id"] == str(new_id)
    assert call_kwargs["payload"]["prior_record_id"] == str(prior.record_id)


def test_audit_event_on_value_conflict() -> None:
    prior = _make_row(canonical_value=6.8)
    detector, audit_repo = _make_detector([prior])
    new_id = uuid.uuid4()
    detector.check(_PATIENT_ID, _CANONICAL_ID, _COLLECTION_DATE, 9.0, new_id)
    audit_repo.record.assert_called_once()
    call_kwargs = audit_repo.record.call_args.kwargs
    assert call_kwargs["event_type"] == "dedup_value_conflict"
    assert call_kwargs["payload"]["value_conflict"] is True


# ── Zero-value edge cases ─────────────────────────────────────────────────────


def test_zero_value_exact_match_is_duplicate() -> None:
    prior = _make_row(canonical_value=0.0)
    detector, _ = _make_detector([prior])
    result = detector.check(_PATIENT_ID, _CANONICAL_ID, _COLLECTION_DATE, 0.0, uuid.uuid4())
    assert result.status == "duplicate"


def test_zero_value_nonzero_new_is_conflict() -> None:
    prior = _make_row(canonical_value=0.0)
    detector, _ = _make_detector([prior])
    result = detector.check(_PATIENT_ID, _CANONICAL_ID, _COLLECTION_DATE, 0.001, uuid.uuid4())
    assert result.status == "value_conflict"
