from __future__ import annotations

from src.ingestion.classification_schemas import Category, ClassificationResult, Subtype

_LAB_REPORT_MSG = "Your lab report has been received and is being processed."

_NOT_SUPPORTED_MSG = "This document type isn't supported by Vitalog. No data has been stored."

_RECOGNIZED_TMPL = (
    "This looks like a {label} — Vitalog currently supports lab reports. "
    "We've saved it and will support this document type in a future update."
)

_SUBTYPE_LABELS: dict[Subtype, str] = {
    Subtype.LAB_PANEL: "lab panel",
    Subtype.IMAGING_REPORT: "imaging report",
    Subtype.DISCHARGE_SUMMARY: "discharge summary",
    Subtype.VISIT_NOTE: "visit note",
    Subtype.PATHOLOGY_REPORT: "pathology report",
    Subtype.PRESCRIPTION: "prescription",
    Subtype.GENETIC_TEST_REPORT: "genetic test report",
    Subtype.PERSONAL_PHOTO: "personal photo",
    Subtype.RECEIPT: "receipt",
    Subtype.SCREENSHOT: "screenshot",
    Subtype.BLANK: "blank document",
    Subtype.UNREADABLE: "unreadable document",
    Subtype.OTHER: "unrecognized document type",
}


def get_user_message(result: ClassificationResult) -> str:
    """Return the user-facing message for a classification result (architecture §5.1)."""
    if result.category == Category.LAB_REPORT:
        return _LAB_REPORT_MSG
    if result.category == Category.NOT_SUPPORTED:
        return _NOT_SUPPORTED_MSG
    label = _SUBTYPE_LABELS.get(result.subtype, "unrecognized document type")
    return _RECOGNIZED_TMPL.format(label=label)
