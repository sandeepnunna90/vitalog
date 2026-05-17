"""Output schemas for the NLQ Handler (F3)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class NlqOutput(BaseModel):
    """LLM tool-use output schema — must match output_schema_name in prompt frontmatter."""

    model_config = ConfigDict(strict=True)

    text: str


class NlqResponse(BaseModel):
    """Public return value from NlqHandler.answer()."""

    model_config = ConfigDict(strict=True)

    text: str
    retrieval_count: int
    prompt_version: str
    is_fallback: bool
