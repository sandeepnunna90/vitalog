"""Pydantic schemas for F6 annotation and export."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Annotation(BaseModel):
    """Patient annotation stored as JSON in SummaryRow.patient_annotations.

    annotation_id is kept as str (not uuid.UUID) for the same reason as SummaryOutputCitation:
    strict=True rejects str→UUID coercion on JSON round-trip from the database.
    """

    model_config = ConfigDict(strict=True)

    annotation_id: str  # UUID string — avoids str→UUID strict-mode rejection on DB round-trip
    section: str
    text: str
    created_at: str  # ISO 8601 string — avoids datetime strict-mode round-trip issues
