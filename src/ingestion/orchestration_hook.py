"""Ingestion pipeline orchestrator — wires validation → classification → storage routing.

The orchestrator implements the short-circuit rule (architecture §7.6 / D3 AC6):
only lab_report documents continue to Textract. The textract_fn slot is left None
until D4 wires the real implementation.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

from pydantic import BaseModel, ConfigDict

from src.ingestion.classification_schemas import Category
from src.ingestion.classifier import DocumentClassifier
from src.ingestion.storage_router import StorageRouter
from src.ingestion.upload_validator import UploadValidator, ValidatedUpload


class IngestionResult(BaseModel):
    model_config = ConfigDict(strict=True)

    category: Category
    document_id: uuid.UUID | None
    user_message: str
    should_continue_pipeline: bool


class IngestionOrchestrator:
    def __init__(
        self,
        validator: UploadValidator,
        classifier: DocumentClassifier,
        storage_router: StorageRouter,
        textract_fn: Callable[[ValidatedUpload, uuid.UUID], None] | None = None,
    ) -> None:
        self._validator = validator
        self._classifier = classifier
        self._storage_router = storage_router
        self._textract_fn = textract_fn

    def process(
        self,
        file_bytes: bytes,
        filename: str,
        patient_id: uuid.UUID,
    ) -> IngestionResult:
        upload = self._validator.validate(file_bytes, filename)
        classification = self._classifier.classify(upload)
        route = self._storage_router.route(upload, classification, patient_id, filename)

        if route.should_continue_pipeline and self._textract_fn is not None:
            assert route.document_id is not None  # always set when should_continue_pipeline=True
            self._textract_fn(upload, route.document_id)

        return IngestionResult(
            category=classification.category,
            document_id=route.document_id,
            user_message=route.user_message,
            should_continue_pipeline=route.should_continue_pipeline,
        )
