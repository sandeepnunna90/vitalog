"""Repository wrapping canonical_biomarker and pending_taxonomy_entry tables."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from supabase import Client

from src.persistence.models import (
    CanonicalBiomarkerRow,
    PendingStatus,
    PendingTaxonomyEntryCreate,
    PendingTaxonomyEntryRow,
)

_CANONICAL_TABLE = "canonical_biomarker"
_PENDING_TABLE = "pending_taxonomy_entry"


class TaxonomyRepository:
    def __init__(self, client: Client) -> None:
        self._client = client

    # ── Canonical biomarker ────────────────────────────────────────────────

    def get_canonical(self, vitalog_id: str) -> CanonicalBiomarkerRow | None:
        """Return a canonical biomarker entry by vitalog_id, or None."""
        data: Any = (
            self._client.table(_CANONICAL_TABLE)
            .select("*")
            .eq("vitalog_id", vitalog_id)
            .execute()
            .data
        )
        return CanonicalBiomarkerRow.model_validate(data[0]) if data else None

    def list_all_canonical(self) -> list[CanonicalBiomarkerRow]:
        """Return all canonical biomarker entries."""
        data: Any = self._client.table(_CANONICAL_TABLE).select("*").execute().data
        return [CanonicalBiomarkerRow.model_validate(row) for row in data]

    # ── Pending taxonomy queue ─────────────────────────────────────────────

    def add_pending(self, entry: PendingTaxonomyEntryCreate) -> PendingTaxonomyEntryRow:
        """Insert a new pending taxonomy entry and return the persisted row."""
        data: Any = (
            self._client.table(_PENDING_TABLE).insert(entry.model_dump(mode="json")).execute().data
        )
        return PendingTaxonomyEntryRow.model_validate(data[0])

    def list_pending(self, status: PendingStatus = "pending") -> list[PendingTaxonomyEntryRow]:
        """Return pending taxonomy entries with the given status."""
        data: Any = (
            self._client.table(_PENDING_TABLE).select("*").eq("status", status).execute().data
        )
        return [PendingTaxonomyEntryRow.model_validate(row) for row in data]

    def resolve_pending(
        self,
        pending_id: uuid.UUID,
        status: PendingStatus,
        resolved_by: str,
    ) -> PendingTaxonomyEntryRow:
        """Update a pending entry to confirmed / rejected / merged."""
        now = datetime.now(tz=UTC).isoformat()
        data: Any = (
            self._client.table(_PENDING_TABLE)
            .update({"status": status, "resolved_at": now, "resolved_by": resolved_by})
            .eq("pending_id", str(pending_id))
            .execute()
            .data
        )
        return PendingTaxonomyEntryRow.model_validate(data[0])
