"""Unit tests for get_user_message — message template selection (architecture §5.1)."""

from __future__ import annotations

from src.ingestion.classification_schemas import Category, ClassificationResult, Subtype
from src.ingestion.user_messages import _SUBTYPE_LABELS, get_user_message


def _result(category: Category, subtype: Subtype, confidence: float = 0.90) -> ClassificationResult:
    return ClassificationResult(
        category=category, subtype=subtype, confidence=confidence, reasoning="test"
    )


# ── AC6: lab_report ───────────────────────────────────────────────────────────


def test_lab_report_message() -> None:
    msg = get_user_message(_result(Category.LAB_REPORT, Subtype.LAB_PANEL))
    assert "lab report" in msg.lower()
    assert "processing" in msg.lower() or "received" in msg.lower()


# ── AC6: recognized_unsupported — subtype label in message ────────────────────


def test_recognized_unsupported_discharge_summary() -> None:
    msg = get_user_message(_result(Category.RECOGNIZED_UNSUPPORTED, Subtype.DISCHARGE_SUMMARY))
    assert "discharge summary" in msg.lower()
    assert "looks like" in msg.lower()


def test_recognized_unsupported_imaging_report() -> None:
    msg = get_user_message(_result(Category.RECOGNIZED_UNSUPPORTED, Subtype.IMAGING_REPORT))
    assert "imaging report" in msg.lower()
    assert "looks like" in msg.lower()


def test_recognized_unsupported_visit_note() -> None:
    msg = get_user_message(_result(Category.RECOGNIZED_UNSUPPORTED, Subtype.VISIT_NOTE))
    assert "visit note" in msg.lower()


# ── AC6: not_supported — generic message, no subtype leak ─────────────────────


def test_not_supported_message() -> None:
    msg = get_user_message(_result(Category.NOT_SUPPORTED, Subtype.PERSONAL_PHOTO))
    assert "not supported" in msg.lower() or "isn't supported" in msg.lower()
    # Must NOT expose internal subtype names in user-facing message.
    assert "personal_photo" not in msg
    assert "PERSONAL_PHOTO" not in msg


# ── All subtypes covered ───────────────────────────────────────────────────────


def test_all_subtypes_covered() -> None:
    """Every Subtype member must have an entry in _SUBTYPE_LABELS."""
    missing = [s for s in Subtype if s not in _SUBTYPE_LABELS]
    assert not missing, f"Subtypes missing from _SUBTYPE_LABELS: {missing}"
