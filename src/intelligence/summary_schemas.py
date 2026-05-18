"""Pydantic schemas for F5 Summary Generator (Mode A)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict

from src.gateway.citation_schemas import Citation


class SummaryOutput(BaseModel):
    """LLM-produced output schema — no disclaimer field (appended by code)."""

    model_config = ConfigDict(strict=True)

    conditions_section: str
    medications_section: str
    results_section: str
    trends_section: str
    data_gaps_section: str
    patient_notes: str
    citations: list[Citation]


class Summary(BaseModel):
    """Final output returned to callers — disclaimer always set by code, never by LLM."""

    model_config = ConfigDict(strict=True)

    patient_id: uuid.UUID
    conditions_section: str
    medications_section: str
    results_section: str
    trends_section: str
    data_gaps_section: str
    patient_notes: str
    citations: list[Citation]
    disclaimer: str
    prompt_version: str
    citation_count: int
    is_fallback: bool
