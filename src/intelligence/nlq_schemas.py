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
    # Condition names whose biomarker groupings were used to expand the query.
    # Non-empty when condition-group expansion fired (e.g. "diabetes" → T2D biomarkers).
    # TODO(G1): surface as a separate structured field in the MCP tool response so the
    # UI can render the disclaimer block independently rather than baking it into text.
    matched_condition_names: list[str] = []
