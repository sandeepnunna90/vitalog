"""Repository for summary table operations."""

from __future__ import annotations

import uuid
from typing import Any

from supabase import Client

from src.persistence.models import SummaryCreate, SummaryRow

_TABLE = "summary"


class SummaryRepository:
    def __init__(self, client: Client) -> None:
        self._client = client

    def add(self, summary: SummaryCreate) -> SummaryRow:
        """Insert a new summary and return the persisted row."""
        data: Any = (
            self._client.table(_TABLE).insert(summary.model_dump(mode="json")).execute().data
        )
        if not data:
            raise ValueError("INSERT returned no rows — possible duplicate or RLS rejection")
        return SummaryRow.model_validate(data[0], strict=False)

    def get(self, summary_id: uuid.UUID) -> SummaryRow | None:
        """Return a summary by its summary_id, or None if not found."""
        data: Any = (
            self._client.table(_TABLE).select("*").eq("summary_id", str(summary_id)).execute().data
        )
        return SummaryRow.model_validate(data[0], strict=False) if data else None

    def list_for_patient(self, patient_id: uuid.UUID) -> list[SummaryRow]:
        """Return all summaries for a patient, newest first."""
        data: Any = (
            self._client.table(_TABLE)
            .select("*")
            .eq("patient_id", str(patient_id))
            .order("generated_at", desc=True)
            .execute()
            .data
        )
        return [SummaryRow.model_validate(row, strict=False) for row in data]

    def update_annotations(self, summary_id: uuid.UUID, annotations: str) -> SummaryRow:
        """Update the patient_annotations field for a summary."""
        data: Any = (
            self._client.table(_TABLE)
            .update({"patient_annotations": annotations})
            .eq("summary_id", str(summary_id))
            .execute()
            .data
        )
        if not data:
            raise ValueError(f"Summary {summary_id} not found or RLS rejected update")
        return SummaryRow.model_validate(data[0], strict=False)
