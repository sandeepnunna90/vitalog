"""Repository for biomarker_record table operations."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from supabase import Client

from src.persistence.models import BiomarkerRecordCreate, BiomarkerRecordRow

_TABLE = "biomarker_record"


class BiomarkerRepository:
    def __init__(self, client: Client) -> None:
        self._client = client

    def add(self, record: BiomarkerRecordCreate) -> BiomarkerRecordRow:
        """Insert a new biomarker record and return the persisted row."""
        data: Any = self._client.table(_TABLE).insert(record.model_dump(mode="json")).execute().data
        return BiomarkerRecordRow.model_validate(data[0])

    def get(self, record_id: uuid.UUID) -> BiomarkerRecordRow | None:
        """Return a single biomarker record by its record_id, or None."""
        data: Any = (
            self._client.table(_TABLE).select("*").eq("record_id", str(record_id)).execute().data
        )
        return BiomarkerRecordRow.model_validate(data[0]) if data else None

    def find_by_canonical_id(
        self, patient_id: uuid.UUID, canonical_id: str
    ) -> list[BiomarkerRecordRow]:
        """Return all records for a patient with a given canonical_biomarker_id."""
        data: Any = (
            self._client.table(_TABLE)
            .select("*")
            .eq("patient_id", str(patient_id))
            .eq("canonical_biomarker_id", canonical_id)
            .order("collection_date", desc=False)
            .execute()
            .data
        )
        return [BiomarkerRecordRow.model_validate(row) for row in data]

    def list_for_patient(self, patient_id: uuid.UUID) -> list[BiomarkerRecordRow]:
        """Return all biomarker records for a patient, ordered by collection_date."""
        data: Any = (
            self._client.table(_TABLE)
            .select("*")
            .eq("patient_id", str(patient_id))
            .order("collection_date", desc=False)
            .execute()
            .data
        )
        return [BiomarkerRecordRow.model_validate(row) for row in data]

    def list_pending_user(self, patient_id: uuid.UUID) -> list[BiomarkerRecordRow]:
        """Return records awaiting user verification for a patient."""
        data: Any = (
            self._client.table(_TABLE)
            .select("*")
            .eq("patient_id", str(patient_id))
            .eq("verified_by", "pending_user")
            .execute()
            .data
        )
        return [BiomarkerRecordRow.model_validate(row) for row in data]

    def find_potential_duplicates(
        self,
        patient_id: uuid.UUID,
        canonical_id: str,
        collection_date: date,
    ) -> list[BiomarkerRecordRow]:
        """Return all records matching patient + canonical_id + exact collection_date."""
        data: Any = (
            self._client.table(_TABLE)
            .select("*")
            .eq("patient_id", str(patient_id))
            .eq("canonical_biomarker_id", canonical_id)
            .eq("collection_date", collection_date.isoformat())
            .execute()
            .data
        )
        return [BiomarkerRecordRow.model_validate(row) for row in data]

    def resolve_pending_records(
        self,
        pending_taxonomy_id: uuid.UUID,
        canonical_biomarker_id: str,
    ) -> int:
        """Bulk-update records linked to a pending entry.

        Sets canonical_biomarker_id and verified_by='admin'. Returns the count updated.
        """
        data: Any = (
            self._client.table(_TABLE)
            .update(
                {
                    "canonical_biomarker_id": canonical_biomarker_id,
                    "verified_by": "admin",
                }
            )
            .eq("pending_taxonomy_id", str(pending_taxonomy_id))
            .execute()
            .data
        )
        return len(data) if data else 0
