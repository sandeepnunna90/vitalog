"""Vitalog ingestion pipeline — upload validation, pre-LLM probes, classification, and routing."""

from src.ingestion.classification_schemas import Category, ClassificationResult, Subtype
from src.ingestion.classifier import DocumentClassifier
from src.ingestion.errors import (
    CorruptOrEmptyError,
    FileTooLargeError,
    IngestionError,
    TextractFailureError,
    UnsupportedFormatError,
)
from src.ingestion.orchestration_hook import IngestionOrchestrator, IngestionResult
from src.ingestion.probes import probe_image, probe_pdf
from src.ingestion.storage_router import StorageRouter, StorageRouteResult
from src.ingestion.textract_adapter import TextractAdapter
from src.ingestion.textract_fallback import FallbackExtractionResult, TextractFallbackAdapter
from src.ingestion.textract_schemas import TextractResult
from src.ingestion.upload_validator import UploadValidator, ValidatedUpload
from src.ingestion.user_messages import get_user_message

__all__ = [
    "UploadValidator",
    "ValidatedUpload",
    "IngestionError",
    "UnsupportedFormatError",
    "FileTooLargeError",
    "CorruptOrEmptyError",
    "TextractFailureError",
    "probe_pdf",
    "probe_image",
    "DocumentClassifier",
    "ClassificationResult",
    "Category",
    "Subtype",
    "get_user_message",
    "StorageRouter",
    "StorageRouteResult",
    "IngestionOrchestrator",
    "IngestionResult",
    "TextractAdapter",
    "TextractFallbackAdapter",
    "FallbackExtractionResult",
    "TextractResult",
]
