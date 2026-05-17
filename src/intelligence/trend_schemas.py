"""Output schemas for the Trend Engine (F1)."""

from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict


class TrendPoint(BaseModel):
    model_config = ConfigDict(strict=True)

    record_id: uuid.UUID
    collection_date: date
    canonical_value: float
    canonical_unit: str
    lab_source: str | None
    verified_by: str
    extraction_confidence: float | None


class TrendBand(BaseModel):
    model_config = ConfigDict(strict=True)

    label: str
    lower: float | None
    upper: float | None
    raw_range: str
    citation: str | None


class TrendResult(BaseModel):
    model_config = ConfigDict(strict=True)

    patient_id: uuid.UUID
    canonical_id: str
    canonical_unit: str | None
    points: list[TrendPoint]
    bands: list[TrendBand]
    pending_review_count: int
