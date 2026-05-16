"""Unit tests for DocumentClassifier — all Gateway calls are mocked."""

from __future__ import annotations

import base64
from typing import Any
from unittest.mock import MagicMock

from src.ingestion.classification_schemas import Category, ClassificationResult, Subtype
from src.ingestion.classifier import DocumentClassifier
from src.ingestion.upload_validator import ValidatedUpload

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_upload(
    file_bytes: bytes,
    mime: str = "application/pdf",
    is_text_extractable: bool | None = True,
) -> ValidatedUpload:
    return ValidatedUpload(
        file_bytes=file_bytes,
        mime=mime,
        size_bytes=len(file_bytes),
        is_text_extractable=is_text_extractable,
        resolution_warning=None,
    )


def _make_result(
    category: Category,
    subtype: Subtype,
    confidence: float,
    reasoning: str = "test reasoning",
) -> ClassificationResult:
    return ClassificationResult(
        category=category, subtype=subtype, confidence=confidence, reasoning=reasoning
    )


def _make_classifier(gateway_return: ClassificationResult) -> DocumentClassifier:
    gateway = MagicMock()
    gateway.call.return_value = gateway_return
    return DocumentClassifier(gateway=gateway)


# ── AC1: lab_report classification ───────────────────────────────────────────


def test_lab_report_returned_as_is(text_pdf_bytes: bytes) -> None:
    expected = _make_result(Category.LAB_REPORT, Subtype.LAB_PANEL, 0.97)
    classifier = _make_classifier(expected)
    result = classifier.classify(_make_upload(text_pdf_bytes))
    assert result.category == Category.LAB_REPORT
    assert result.subtype == Subtype.LAB_PANEL
    assert result.confidence == 0.97


# ── AC2: recognized_unsupported preserves subtype ────────────────────────────


def test_recognized_unsupported_subtype_preserved(text_pdf_bytes: bytes) -> None:
    expected = _make_result(Category.RECOGNIZED_UNSUPPORTED, Subtype.DISCHARGE_SUMMARY, 0.88)
    classifier = _make_classifier(expected)
    result = classifier.classify(_make_upload(text_pdf_bytes))
    assert result.category == Category.RECOGNIZED_UNSUPPORTED
    assert result.subtype == Subtype.DISCHARGE_SUMMARY


# ── AC3: not_supported for personal photo ────────────────────────────────────


def test_not_supported_personal_photo(high_res_jpeg_bytes: bytes) -> None:
    expected = _make_result(Category.NOT_SUPPORTED, Subtype.PERSONAL_PHOTO, 0.92)
    classifier = _make_classifier(expected)
    upload = _make_upload(high_res_jpeg_bytes, mime="image/jpeg", is_text_extractable=None)
    result = classifier.classify(upload)
    assert result.category == Category.NOT_SUPPORTED
    assert result.subtype == Subtype.PERSONAL_PHOTO


# ── AC4: conservative bias override ──────────────────────────────────────────


def test_low_confidence_overrides_to_not_supported(text_pdf_bytes: bytes) -> None:
    raw = _make_result(Category.LAB_REPORT, Subtype.LAB_PANEL, 0.55)
    classifier = _make_classifier(raw)
    result = classifier.classify(_make_upload(text_pdf_bytes))
    assert result.category == Category.NOT_SUPPORTED
    assert result.confidence == 0.55
    assert "Conservative bias applied" in result.reasoning
    assert "0.55" in result.reasoning


def test_exact_07_confidence_not_overridden(text_pdf_bytes: bytes) -> None:
    raw = _make_result(Category.LAB_REPORT, Subtype.LAB_PANEL, 0.70)
    classifier = _make_classifier(raw)
    result = classifier.classify(_make_upload(text_pdf_bytes))
    assert result.category == Category.LAB_REPORT


def test_conservative_bias_preserves_subtype(text_pdf_bytes: bytes) -> None:
    raw = _make_result(Category.RECOGNIZED_UNSUPPORTED, Subtype.VISIT_NOTE, 0.60)
    classifier = _make_classifier(raw)
    result = classifier.classify(_make_upload(text_pdf_bytes))
    assert result.category == Category.NOT_SUPPORTED
    assert result.subtype == Subtype.VISIT_NOTE


# ── PDF path: text extraction, not vision ────────────────────────────────────


def test_pdf_uses_text_not_image_content(text_pdf_bytes: bytes) -> None:
    gateway = MagicMock()
    gateway.call.return_value = _make_result(Category.LAB_REPORT, Subtype.LAB_PANEL, 0.95)
    classifier = DocumentClassifier(gateway=gateway)
    classifier.classify(_make_upload(text_pdf_bytes))

    _, call_kwargs = gateway.call.call_args
    assert call_kwargs.get("image_content") is None
    positional_inputs: dict[str, Any] = gateway.call.call_args.args[2]
    assert "document_text" in positional_inputs
    assert len(positional_inputs["document_text"]) > 0


def test_blank_pdf_uses_placeholder(image_pdf_bytes: bytes) -> None:
    """Image-only PDF → PyMuPDF extracts empty text → placeholder injected."""
    gateway = MagicMock()
    gateway.call.return_value = _make_result(Category.NOT_SUPPORTED, Subtype.BLANK, 0.85)
    classifier = DocumentClassifier(gateway=gateway)
    classifier.classify(_make_upload(image_pdf_bytes, is_text_extractable=False))

    positional_inputs: dict[str, Any] = gateway.call.call_args.args[2]
    assert positional_inputs["document_text"] == "[PDF has no extractable text]"


# ── Image path: vision block ──────────────────────────────────────────────────


def test_image_sends_vision_block(high_res_jpeg_bytes: bytes) -> None:
    gateway = MagicMock()
    gateway.call.return_value = _make_result(Category.NOT_SUPPORTED, Subtype.PERSONAL_PHOTO, 0.90)
    classifier = DocumentClassifier(gateway=gateway)
    upload = _make_upload(high_res_jpeg_bytes, mime="image/jpeg", is_text_extractable=None)
    classifier.classify(upload)

    _, call_kwargs = gateway.call.call_args
    image_content = call_kwargs.get("image_content")
    assert image_content is not None
    assert len(image_content) == 1
    block = image_content[0]
    assert block["type"] == "image"
    assert block["source"]["type"] == "base64"
    assert block["source"]["media_type"] == "image/jpeg"
    # Verify the base64 data decodes back to the original bytes.
    decoded = base64.standard_b64decode(block["source"]["data"])
    assert decoded == high_res_jpeg_bytes


# ── Gateway called with correct identifiers ───────────────────────────────────


def test_gateway_called_with_correct_prompt_id(text_pdf_bytes: bytes) -> None:
    gateway = MagicMock()
    gateway.call.return_value = _make_result(Category.LAB_REPORT, Subtype.LAB_PANEL, 0.95)
    classifier = DocumentClassifier(gateway=gateway)
    classifier.classify(_make_upload(text_pdf_bytes))

    args = gateway.call.call_args.args
    assert args[0] == "classification"
    assert args[1] == "v1"
    assert args[3] is ClassificationResult
