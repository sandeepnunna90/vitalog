from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class Category(StrEnum):
    LAB_REPORT = "lab_report"
    RECOGNIZED_UNSUPPORTED = "recognized_unsupported"
    NOT_SUPPORTED = "not_supported"


class Subtype(StrEnum):
    LAB_PANEL = "lab_panel"
    IMAGING_REPORT = "imaging_report"
    DISCHARGE_SUMMARY = "discharge_summary"
    VISIT_NOTE = "visit_note"
    PATHOLOGY_REPORT = "pathology_report"
    PRESCRIPTION = "prescription"
    GENETIC_TEST_REPORT = "genetic_test_report"
    PERSONAL_PHOTO = "personal_photo"
    RECEIPT = "receipt"
    SCREENSHOT = "screenshot"
    BLANK = "blank"
    UNREADABLE = "unreadable"
    OTHER = "other"


class ClassificationResult(BaseModel):
    model_config = ConfigDict(strict=True)

    category: Category
    subtype: Subtype
    confidence: float
    reasoning: str
