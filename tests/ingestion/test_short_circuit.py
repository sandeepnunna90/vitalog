"""Short-circuit tests for IngestionOrchestrator (D3 AC6).

Verifies that textract_fn is only called for lab_report documents;
recognized_unsupported and not_supported stop the pipeline before Textract.

All three pipeline components (validator, classifier, storage_router) are
replaced with MagicMocks so these tests exercise only orchestration logic.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

from src.ingestion.classification_schemas import Category, ClassificationResult, Subtype
from src.ingestion.orchestration_hook import IngestionOrchestrator, IngestionResult
from src.ingestion.storage_router import StorageRouteResult
from src.ingestion.upload_validator import ValidatedUpload

_PATIENT_ID = uuid.UUID("00000000-0000-0000-0000-000000000099")
_DOC_ID = uuid.UUID("00000000-0000-0000-0000-000000000088")


def _make_upload() -> ValidatedUpload:
    return ValidatedUpload(
        file_bytes=b"data",
        mime="application/pdf",
        size_bytes=4,
        is_text_extractable=True,
        resolution_warning=None,
    )


def _make_classification(category: Category, subtype: Subtype) -> ClassificationResult:
    return ClassificationResult(
        category=category,
        subtype=subtype,
        confidence=0.95,
        reasoning="test",
    )


def _make_orchestrator(
    category: Category,
    subtype: Subtype,
    should_continue: bool,
    textract_fn: MagicMock | None = None,
) -> IngestionOrchestrator:
    validator = MagicMock()
    classifier = MagicMock()
    storage_router = MagicMock()

    upload = _make_upload()
    classification = _make_classification(category, subtype)

    validator.validate.return_value = upload
    classifier.classify.return_value = classification
    storage_router.route.return_value = StorageRouteResult(
        document_id=_DOC_ID if should_continue else None,
        storage_uri="supabase-storage://bucket/path" if should_continue else "discard://x",
        user_message="test message",
        should_continue_pipeline=should_continue,
    )

    return IngestionOrchestrator(
        validator=validator,
        classifier=classifier,
        storage_router=storage_router,
        textract_fn=textract_fn,
    )


def test_textract_called_for_lab_report() -> None:
    textract_fn = MagicMock()
    orchestrator = _make_orchestrator(
        Category.LAB_REPORT, Subtype.LAB_PANEL, should_continue=True, textract_fn=textract_fn
    )
    orchestrator.process(b"data", "lab.pdf", _PATIENT_ID)
    textract_fn.assert_called_once()


def test_textract_not_called_for_recognized_unsupported() -> None:
    textract_fn = MagicMock()
    orchestrator = _make_orchestrator(
        Category.RECOGNIZED_UNSUPPORTED,
        Subtype.DISCHARGE_SUMMARY,
        should_continue=False,
        textract_fn=textract_fn,
    )
    orchestrator.process(b"data", "discharge.pdf", _PATIENT_ID)
    textract_fn.assert_not_called()


def test_textract_not_called_for_not_supported() -> None:
    textract_fn = MagicMock()
    orchestrator = _make_orchestrator(
        Category.NOT_SUPPORTED,
        Subtype.PERSONAL_PHOTO,
        should_continue=False,
        textract_fn=textract_fn,
    )
    orchestrator.process(b"data", "cat.jpg", _PATIENT_ID)
    textract_fn.assert_not_called()


def test_result_carries_category_and_message() -> None:
    orchestrator = _make_orchestrator(
        Category.RECOGNIZED_UNSUPPORTED,
        Subtype.IMAGING_REPORT,
        should_continue=False,
    )
    result = orchestrator.process(b"data", "scan.pdf", _PATIENT_ID)

    assert isinstance(result, IngestionResult)
    assert result.category == Category.RECOGNIZED_UNSUPPORTED
    assert result.user_message == "test message"
    assert result.should_continue_pipeline is False
    assert result.document_id is None
