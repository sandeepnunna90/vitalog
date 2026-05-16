"""Classification-gated storage router (architecture §7.6).

Routes a ValidatedUpload to the correct persistence path based on its
ClassificationResult:
  lab_report             → stored permanently; document row inserted; pipeline continues
  recognized_unsupported → stored permanently; document row inserted; pipeline stops
  not_supported          → file discarded; audit metadata only; pipeline stops
"""

from __future__ import annotations

import hashlib
import uuid

from pydantic import BaseModel, ConfigDict

from src.ingestion.classification_schemas import Category, ClassificationResult
from src.ingestion.upload_validator import ValidatedUpload
from src.ingestion.user_messages import get_user_message
from src.persistence.audit_log_repository import AuditLogRepository
from src.persistence.document_repository import DocumentRepository
from src.persistence.document_store import DocumentStore
from src.persistence.models import DocumentCreate


class StorageRouteResult(BaseModel):
    model_config = ConfigDict(strict=True)

    document_id: uuid.UUID | None
    storage_uri: str
    user_message: str
    should_continue_pipeline: bool


class StorageRouter:
    def __init__(
        self,
        document_store: DocumentStore,
        doc_repo: DocumentRepository,
        audit_repo: AuditLogRepository,
    ) -> None:
        self._store = document_store
        self._doc_repo = doc_repo
        self._audit = audit_repo

    def route(
        self,
        upload: ValidatedUpload,
        result: ClassificationResult,
        patient_id: uuid.UUID,
        filename: str,
    ) -> StorageRouteResult:
        if result.category == Category.LAB_REPORT:
            return self._route_lab_report(upload, result, patient_id, filename)
        if result.category == Category.RECOGNIZED_UNSUPPORTED:
            return self._route_recognized_unsupported(upload, result, patient_id, filename)
        return self._route_not_supported(upload, result, patient_id, filename)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _route_lab_report(
        self,
        upload: ValidatedUpload,
        result: ClassificationResult,
        patient_id: uuid.UUID,
        filename: str,
    ) -> StorageRouteResult:
        uri = self._store.put(upload.file_bytes, filename, patient_id, "permanent")
        doc = self._doc_repo.add(
            DocumentCreate(
                patient_id=patient_id,
                classification="lab_report",
                raw_storage_uri=uri,
                processing_status="pending",
            )
        )
        self._audit.record(
            "system",
            "document_uploaded",
            {
                "document_id": str(doc.document_id),
                "patient_id": str(patient_id),
                "classification": "lab_report",
                "subtype": str(result.subtype),
                "confidence": result.confidence,
                "storage_uri": uri,
            },
        )
        return StorageRouteResult(
            document_id=doc.document_id,
            storage_uri=uri,
            user_message=get_user_message(result),
            should_continue_pipeline=True,
        )

    def _route_recognized_unsupported(
        self,
        upload: ValidatedUpload,
        result: ClassificationResult,
        patient_id: uuid.UUID,
        filename: str,
    ) -> StorageRouteResult:
        uri = self._store.put(upload.file_bytes, filename, patient_id, "permanent")
        doc = self._doc_repo.add(
            DocumentCreate(
                patient_id=patient_id,
                classification="recognized_unsupported",
                raw_storage_uri=uri,
                processing_status="complete",
            )
        )
        self._audit.record(
            "system",
            "document_classified_unsupported",
            {
                "document_id": str(doc.document_id),
                "patient_id": str(patient_id),
                "classification": "recognized_unsupported",
                "subtype": str(result.subtype),
                "confidence": result.confidence,
                "storage_uri": uri,
            },
        )
        return StorageRouteResult(
            document_id=doc.document_id,
            storage_uri=uri,
            user_message=get_user_message(result),
            should_continue_pipeline=False,
        )

    def _route_not_supported(
        self,
        upload: ValidatedUpload,
        result: ClassificationResult,
        patient_id: uuid.UUID,
        filename: str,
    ) -> StorageRouteResult:
        uri = self._store.put(
            upload.file_bytes, filename, patient_id, "discard_after_classification"
        )
        file_hash = hashlib.sha256(upload.file_bytes).hexdigest()
        self._audit.record(
            "system",
            "document_classified_not_supported",
            {
                "patient_id": str(patient_id),
                "filename": filename,
                "mime": upload.mime,
                "size_bytes": upload.size_bytes,
                "sha256": file_hash,
                "classification": "not_supported",
                "subtype": str(result.subtype),
                "confidence": result.confidence,
                "reasoning": result.reasoning,
            },
        )
        return StorageRouteResult(
            document_id=None,
            storage_uri=uri,
            user_message=get_user_message(result),
            should_continue_pipeline=False,
        )
