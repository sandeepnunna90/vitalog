"""Output schemas for the Observation Generator (F2)."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict


class ObservationCitation(BaseModel):
    model_config = ConfigDict(strict=True)

    kind: Literal["record", "guideline"]
    # record_id is a string because the LLM always returns strings in JSON tool-use output.
    # Strict mode would reject a str→UUID coercion.
    record_id: str | None = None
    source: str | None = None
    range: str | None = None


class ObservationOutput(BaseModel):
    """LLM tool-use output schema — must match output_schema_name in prompt frontmatter."""

    model_config = ConfigDict(strict=True)

    text: str
    citations: list[ObservationCitation]


class Observation(BaseModel):
    """Public return value from ObservationGenerator.generate()."""

    model_config = ConfigDict(strict=True)

    record_id: uuid.UUID
    text: str
    citations: list[ObservationCitation]
    prompt_version: str
