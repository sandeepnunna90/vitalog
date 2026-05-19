"""Pydantic schemas for F5 Summary Generator (Mode A)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict

from src.gateway.citation_schemas import Citation


class SummaryOutputCitation(BaseModel):
    """LLM-returned citation — dates and UUIDs arrive as strings in JSON tool-use output.

    Pydantic strict=True rejects str→date and str→UUID coercion, so this mirrors
    the ObservationCitation pattern: keep string types here, convert to Citation
    (with proper types) after parsing and before verify_mode_a().
    """

    model_config = ConfigDict(strict=True)

    value: float
    unit: str
    collection_date: str  # "YYYY-MM-DD" string from LLM
    source_record_id: str  # UUID string from LLM


class SummaryOutput(BaseModel):
    """LLM-produced output schema — no disclaimer field (appended by code)."""

    model_config = ConfigDict(strict=True)

    conditions_section: str
    results_section: str
    trends_section: str
    data_gaps_section: str
    patient_notes: str
    citations: list[SummaryOutputCitation]


class Summary(BaseModel):
    """Final output returned to callers — disclaimer always set by code, never by LLM."""

    model_config = ConfigDict(strict=True)

    patient_id: uuid.UUID
    conditions_section: str
    results_section: str
    trends_section: str
    data_gaps_section: str
    patient_notes: str
    citations: list[Citation]
    disclaimer: str
    prompt_version: str
    citation_count: int
    is_fallback: bool
