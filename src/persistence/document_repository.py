"""Repository for document table operations."""

from __future__ import annotations

import uuid
from typing import Any

from supabase import Client

from src.persistence.models import DocumentCreate, DocumentRow, ProcessingStatus

_TABLE = "document"


class DocumentRepository:
    def __init__(self, client: Client) -> None:
        self._client = client

    def add(self, doc: DocumentCreate) -> DocumentRow:
        """Insert a new document record and return the persisted row."""
        data: Any = self._client.table(_TABLE).insert(doc.model_dump(mode="json")).execute().data
        if not data:
            raise ValueError("INSERT returned no rows — possible duplicate or RLS rejection")
        return DocumentRow.model_validate(data[0])

    def get_by_id(self, document_id: uuid.UUID) -> DocumentRow | None:
        """Return a document by its document_id, or None if not found."""
        data: Any = (
            self._client.table(_TABLE)
            .select("*")
            .eq("document_id", str(document_id))
            .execute()
            .data
        )
        return DocumentRow.model_validate(data[0]) if data else None

    def list_for_patient(self, patient_id: uuid.UUID) -> list[DocumentRow]:
        """Return all documents for a patient, newest first."""
        data: Any = (
            self._client.table(_TABLE)
            .select("*")
            .eq("patient_id", str(patient_id))
            .order("uploaded_at", desc=True)
            .execute()
            .data
        )
        return [DocumentRow.model_validate(row) for row in data]

    def update_processing_status(
        self, document_id: uuid.UUID, status: ProcessingStatus
    ) -> DocumentRow:
        """Update the processing_status field for a document."""
        data: Any = (
            self._client.table(_TABLE)
            .update({"processing_status": status})
            .eq("document_id", str(document_id))
            .execute()
            .data
        )
        if not data:
            raise ValueError(f"Document {document_id} not found or RLS rejected update")
        return DocumentRow.model_validate(data[0])
