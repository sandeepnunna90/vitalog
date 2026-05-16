"""Unit tests for StorageRouter — all three classification branches.

All external dependencies (DocumentStore, DocumentRepository, AuditLogRepository)
are mocked. doc_repo.add returns a synthetic DocumentRow so the router can read
document_id without hitting Supabase.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

from src.ingestion.classification_schemas import Category, ClassificationResult, Subtype
from src.ingestion.storage_router import StorageRouter
from src.ingestion.upload_validator import ValidatedUpload
from src.persistence.models import DocumentRow

# ── Helpers ───────────────────────────────────────────────────────────────────

_PATIENT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
_DOC_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
_STORAGE_URI = "supabase-storage://lab-reports/some/path"


def _make_upload(file_bytes: bytes = b"content", mime: str = "application/pdf") -> ValidatedUpload:
    return ValidatedUpload(
        file_bytes=file_bytes,
        mime=mime,
        size_bytes=len(file_bytes),
        is_text_extractable=True,
        resolution_warning=None,
    )


def _make_result(
    category: Category,
    subtype: Subtype,
    confidence: float = 0.95,
) -> ClassificationResult:
    return ClassificationResult(
        category=category,
        subtype=subtype,
        confidence=confidence,
        reasoning="test reasoning",
    )


def _make_doc_row(classification: str) -> DocumentRow:
    return DocumentRow(
        document_id=_DOC_ID,
        patient_id=_PATIENT_ID,
        raw_storage_uri=_STORAGE_URI,
        classification=classification,  # type: ignore[arg-type]
        uploaded_at=datetime.now(tz=UTC),
        processing_status="pending",
    )


def _make_router() -> tuple[StorageRouter, MagicMock, MagicMock, MagicMock]:
    store = MagicMock()
    doc_repo = MagicMock()
    audit_repo = MagicMock()
    router = StorageRouter(
        document_store=store,
        doc_repo=doc_repo,
        audit_repo=audit_repo,
    )
    return router, store, doc_repo, audit_repo


# ── lab_report tests ──────────────────────────────────────────────────────────


def test_lab_report_stores_permanently() -> None:
    router, store, doc_repo, _ = _make_router()
    store.put.return_value = _STORAGE_URI
    doc_repo.add.return_value = _make_doc_row("lab_report")

    upload = _make_upload()
    result = _make_result(Category.LAB_REPORT, Subtype.LAB_PANEL)
    router.route(upload, result, _PATIENT_ID, "lab.pdf")

    store.put.assert_called_once()
    _, _, _, policy = store.put.call_args.args
    assert policy == "permanent"


def test_lab_report_inserts_document_row() -> None:
    router, store, doc_repo, _ = _make_router()
    store.put.return_value = _STORAGE_URI
    doc_row = _make_doc_row("lab_report")
    doc_repo.add.return_value = doc_row

    upload = _make_upload()
    result = _make_result(Category.LAB_REPORT, Subtype.LAB_PANEL)
    route_result = router.route(upload, result, _PATIENT_ID, "lab.pdf")

    doc_repo.add.assert_called_once()
    assert route_result.document_id == doc_row.document_id


def test_lab_report_writes_document_uploaded_audit() -> None:
    router, store, doc_repo, audit = _make_router()
    store.put.return_value = _STORAGE_URI
    doc_repo.add.return_value = _make_doc_row("lab_report")

    upload = _make_upload()
    result = _make_result(Category.LAB_REPORT, Subtype.LAB_PANEL)
    router.route(upload, result, _PATIENT_ID, "lab.pdf")

    audit.record.assert_called_once()
    _, event_type, _ = audit.record.call_args.args
    assert event_type == "document_uploaded"


def test_lab_report_should_continue_pipeline() -> None:
    router, store, doc_repo, _ = _make_router()
    store.put.return_value = _STORAGE_URI
    doc_repo.add.return_value = _make_doc_row("lab_report")

    upload = _make_upload()
    result = _make_result(Category.LAB_REPORT, Subtype.LAB_PANEL)
    route_result = router.route(upload, result, _PATIENT_ID, "lab.pdf")

    assert route_result.should_continue_pipeline is True


# ── recognized_unsupported tests ──────────────────────────────────────────────


def test_recognized_unsupported_stores_permanently() -> None:
    router, store, doc_repo, _ = _make_router()
    store.put.return_value = _STORAGE_URI
    doc_repo.add.return_value = _make_doc_row("recognized_unsupported")

    upload = _make_upload()
    result = _make_result(Category.RECOGNIZED_UNSUPPORTED, Subtype.DISCHARGE_SUMMARY)
    router.route(upload, result, _PATIENT_ID, "discharge.pdf")

    _, _, _, policy = store.put.call_args.args
    assert policy == "permanent"


def test_recognized_unsupported_returns_roadmap_message() -> None:
    """PRD Scenario 9 — discharge summary gets a subtype-specific roadmap message."""
    router, store, doc_repo, _ = _make_router()
    store.put.return_value = _STORAGE_URI
    doc_repo.add.return_value = _make_doc_row("recognized_unsupported")

    upload = _make_upload()
    result = _make_result(Category.RECOGNIZED_UNSUPPORTED, Subtype.DISCHARGE_SUMMARY)
    route_result = router.route(upload, result, _PATIENT_ID, "discharge.pdf")

    assert "discharge summary" in route_result.user_message


def test_recognized_unsupported_audit() -> None:
    router, store, doc_repo, audit = _make_router()
    store.put.return_value = _STORAGE_URI
    doc_repo.add.return_value = _make_doc_row("recognized_unsupported")

    upload = _make_upload()
    result = _make_result(Category.RECOGNIZED_UNSUPPORTED, Subtype.DISCHARGE_SUMMARY)
    router.route(upload, result, _PATIENT_ID, "discharge.pdf")

    _, event_type, _ = audit.record.call_args.args
    assert event_type == "document_classified_unsupported"


def test_recognized_unsupported_should_not_continue_pipeline() -> None:
    router, store, doc_repo, _ = _make_router()
    store.put.return_value = _STORAGE_URI
    doc_repo.add.return_value = _make_doc_row("recognized_unsupported")

    upload = _make_upload()
    result = _make_result(Category.RECOGNIZED_UNSUPPORTED, Subtype.IMAGING_REPORT)
    route_result = router.route(upload, result, _PATIENT_ID, "scan.pdf")

    assert route_result.should_continue_pipeline is False


# ── not_supported tests ───────────────────────────────────────────────────────


def test_not_supported_discards_file() -> None:
    """PRD Scenario 10 — personal photo is discarded; no document row inserted."""
    router, store, doc_repo, _ = _make_router()
    store.put.return_value = "discard://some-uuid"

    upload = _make_upload(mime="image/jpeg")
    result = _make_result(Category.NOT_SUPPORTED, Subtype.PERSONAL_PHOTO)
    router.route(upload, result, _PATIENT_ID, "cat.jpg")

    _, _, _, policy = store.put.call_args.args
    assert policy == "discard_after_classification"
    doc_repo.add.assert_not_called()


def test_not_supported_audit_has_metadata() -> None:
    store, audit = MagicMock(), MagicMock()
    doc_repo = MagicMock()
    router_obj = StorageRouter(document_store=store, doc_repo=doc_repo, audit_repo=audit)
    store.put.return_value = "discard://some-uuid"

    file_bytes = b"fake image data"
    upload = ValidatedUpload(
        file_bytes=file_bytes,
        mime="image/jpeg",
        size_bytes=len(file_bytes),
        is_text_extractable=None,
        resolution_warning=None,
    )
    result = _make_result(Category.NOT_SUPPORTED, Subtype.PERSONAL_PHOTO)
    router_obj.route(upload, result, _PATIENT_ID, "cat.jpg")

    _, event_type, payload = audit.record.call_args.args
    assert event_type == "document_classified_not_supported"
    assert payload["filename"] == "cat.jpg"
    assert payload["mime"] == "image/jpeg"
    assert payload["size_bytes"] == len(file_bytes)
    assert payload["sha256"] == hashlib.sha256(file_bytes).hexdigest()


def test_not_supported_returns_generic_message() -> None:
    router, store, doc_repo, _ = _make_router()
    store.put.return_value = "discard://some-uuid"

    upload = _make_upload(mime="image/jpeg")
    result = _make_result(Category.NOT_SUPPORTED, Subtype.PERSONAL_PHOTO)
    route_result = router.route(upload, result, _PATIENT_ID, "cat.jpg")

    assert "supported" in route_result.user_message.lower()
    assert route_result.document_id is None
    assert route_result.should_continue_pipeline is False
