"""Pydantic models for F4 context cards (deterministic reference-data composition)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class _Base(BaseModel):
    model_config = ConfigDict(strict=True)


class RangeWithCitation(_Base):
    label: str
    value: str
    unit: str
    source: str
    source_section: str | None


class ContextCard(_Base):
    vitalog_id: str
    canonical_name: str
    definition: str
    relevance: str
    ranges_with_citations: list[RangeWithCitation]
    disclaimer: str


class CardNotAvailable(_Base):
    vitalog_id: str
    reason: str
