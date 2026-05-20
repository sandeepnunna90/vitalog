"""Pydantic schemas for the D6 Structurer — biomarker candidate extraction and band routing."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field


def _to_float(v: Any) -> float:
    return float(v)


class Band(StrEnum):
    AUTO_ACCEPT = "auto_accept"
    REVIEW = "review"
    REJECT = "reject"


class RawBiomarkerCandidate(BaseModel):
    """One biomarker reading as emitted by the LLM (Gateway tool-use output).

    Values are raw strings as-extracted — no parsing or unit conversion.
    Parsing happens downstream in Normalization (E3).
    """

    model_config = ConfigDict(strict=True)

    raw_name: str
    raw_value: str
    raw_unit: str
    raw_reference_range: str
    collection_date: str  # LLM-emitted string; must be ISO 8601 (YYYY-MM-DD) for DB insert
    lab_source: str
    llm_confidence: Annotated[float, BeforeValidator(_to_float)] = Field(ge=0.0, le=100.0)
    source_page: int | None


class StructuredReport(BaseModel):
    """Top-level Gateway output schema for prompt structurer/v1.

    output_schema_name in the prompt frontmatter must match this class name exactly.
    """

    model_config = ConfigDict(strict=True)

    candidates: list[RawBiomarkerCandidate]
    extraction_notes: str


class BiomarkerCandidate(BaseModel):
    """Public output of the Structurer — raw candidate enriched with composite confidence and band.

    Downstream consumers (Normalization, Persistence) use this type exclusively.
    """

    model_config = ConfigDict(strict=True)

    raw_name: str
    raw_value: str
    raw_unit: str
    raw_reference_range: str
    collection_date: str  # must be ISO 8601 (YYYY-MM-DD); non-ISO raises Postgres error on insert
    lab_source: str
    llm_confidence: float
    source_page: int | None
    composite_confidence: float = Field(ge=0.0, le=100.0)
    band: Band
