"""Unit tests for UploadValidator — AC1 through AC6 plus audit behaviour."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.ingestion.errors import CorruptOrEmptyError, FileTooLargeError, UnsupportedFormatError
from src.ingestion.upload_validator import UploadValidator, ValidatedUpload


@pytest.fixture()
def validator() -> UploadValidator:
    return UploadValidator()


@pytest.fixture()
def mock_audit() -> MagicMock:
    return MagicMock()


@pytest.fixture()
def audited_validator(mock_audit: MagicMock) -> UploadValidator:
    return UploadValidator(audit_repo=mock_audit)


# ── AC 1: Unsupported format ──────────────────────────────────────────────────


def test_docx_raises_unsupported(validator: UploadValidator, docx_bytes: bytes) -> None:
    """AC1: ZIP-magic bytes (docx) → UnsupportedFormatError naming supported set."""
    with pytest.raises(UnsupportedFormatError) as exc_info:
        validator.validate(docx_bytes, "report.docx")
    err = exc_info.value
    assert "PDF" in str(err)
    assert "HEIC" in str(err)
    assert err.detected_mime is not None


def test_random_bytes_raise_unsupported(validator: UploadValidator) -> None:
    """AC1: unrecognised bytes → UnsupportedFormatError."""
    with pytest.raises(UnsupportedFormatError):
        validator.validate(b"\x00\x01\x02\x03" * 20, "garbage.bin")


# ── AC 2: File too large ──────────────────────────────────────────────────────


def test_oversized_file_raises(validator: UploadValidator, oversized_pdf_bytes: bytes) -> None:
    """AC2: file > 20 MB → FileTooLargeError."""
    with pytest.raises(FileTooLargeError) as exc_info:
        validator.validate(oversized_pdf_bytes, "big.pdf")
    err = exc_info.value
    assert err.size_bytes > 20 * 1024 * 1024
    assert err.max_bytes == 20 * 1024 * 1024


def test_custom_max_bytes_respected(text_pdf_bytes: bytes) -> None:
    """AC2: size cap is configurable via constructor."""
    tiny_cap = UploadValidator(max_bytes=10)
    with pytest.raises(FileTooLargeError):
        tiny_cap.validate(text_pdf_bytes, "any.pdf")


# ── AC 3: Empty or corrupt ────────────────────────────────────────────────────


def test_empty_file_raises(validator: UploadValidator, empty_bytes: bytes) -> None:
    """AC3a: 0 bytes → CorruptOrEmptyError mentioning '0 bytes'."""
    with pytest.raises(CorruptOrEmptyError) as exc_info:
        validator.validate(empty_bytes, "empty.pdf")
    assert "0 bytes" in str(exc_info.value)


def test_corrupt_pdf_raises(validator: UploadValidator, corrupt_pdf_bytes: bytes) -> None:
    """AC3b: bytes sniff as PDF but PyMuPDF cannot open → CorruptOrEmptyError."""
    with pytest.raises(CorruptOrEmptyError):
        validator.validate(corrupt_pdf_bytes, "corrupt.pdf")


def test_corrupt_image_raises(validator: UploadValidator, corrupt_image_bytes: bytes) -> None:
    """AC3c: JPEG magic bytes but corrupt body → CorruptOrEmptyError."""
    with pytest.raises(CorruptOrEmptyError):
        validator.validate(corrupt_image_bytes, "corrupt.jpg")


# ── AC 4: PDF text-extractable probe ─────────────────────────────────────────


def test_text_pdf_is_extractable(validator: UploadValidator, text_pdf_bytes: bytes) -> None:
    """AC4a: text-bearing PDF → is_text_extractable=True."""
    result = validator.validate(text_pdf_bytes, "lab.pdf")
    assert isinstance(result, ValidatedUpload)
    assert result.is_text_extractable is True
    assert result.mime == "application/pdf"


def test_image_pdf_not_extractable(validator: UploadValidator, image_pdf_bytes: bytes) -> None:
    """AC4b: image-only PDF → is_text_extractable=False."""
    result = validator.validate(image_pdf_bytes, "scan.pdf")
    assert result.is_text_extractable is False


def test_image_upload_has_none_extractable(
    validator: UploadValidator, high_res_jpeg_bytes: bytes
) -> None:
    """AC4c: image upload → is_text_extractable=None (not applicable)."""
    result = validator.validate(high_res_jpeg_bytes, "photo.jpg")
    assert result.is_text_extractable is None


# ── AC 5: Image resolution probe ─────────────────────────────────────────────


def test_high_res_jpeg_no_warning(validator: UploadValidator, high_res_jpeg_bytes: bytes) -> None:
    """AC5a: 800×800 JPEG → resolution_warning=None, file accepted."""
    result = validator.validate(high_res_jpeg_bytes, "hires.jpg")
    assert isinstance(result, ValidatedUpload)
    assert result.resolution_warning is None


def test_low_res_jpeg_warning_not_rejection(
    validator: UploadValidator, low_res_jpeg_bytes: bytes
) -> None:
    """AC5b: 400×400 JPEG → warning string, but ValidatedUpload is still returned."""
    result = validator.validate(low_res_jpeg_bytes, "lowres.jpg")
    assert isinstance(result, ValidatedUpload)
    assert result.resolution_warning is not None
    assert "400" in result.resolution_warning


def test_png_no_warning(validator: UploadValidator, high_res_png_bytes: bytes) -> None:
    """AC5c: 1000×1000 PNG → no warning."""
    result = validator.validate(high_res_png_bytes, "chart.png")
    assert result.resolution_warning is None


def test_pdf_has_no_resolution_warning(validator: UploadValidator, text_pdf_bytes: bytes) -> None:
    """AC5d: PDF → resolution_warning=None (not applicable)."""
    result = validator.validate(text_pdf_bytes, "report.pdf")
    assert result.resolution_warning is None


# ── AC 6: ValidatedUpload carries all required fields ────────────────────────


def test_validated_upload_all_fields(validator: UploadValidator, text_pdf_bytes: bytes) -> None:
    """AC6: ValidatedUpload exposes file_bytes, mime, size_bytes, probes."""
    result = validator.validate(text_pdf_bytes, "report.pdf")
    assert result.file_bytes == text_pdf_bytes
    assert result.mime == "application/pdf"
    assert result.size_bytes == len(text_pdf_bytes)
    assert isinstance(result.is_text_extractable, bool)
    assert result.resolution_warning is None


# ── Audit log behaviour ───────────────────────────────────────────────────────


def test_audit_recorded_on_pass(
    audited_validator: UploadValidator,
    mock_audit: MagicMock,
    text_pdf_bytes: bytes,
) -> None:
    """Audit fires with validation_result='pass' on success."""
    audited_validator.validate(text_pdf_bytes, "lab.pdf")
    mock_audit.record.assert_called_once()
    kwargs = mock_audit.record.call_args.kwargs
    assert kwargs["actor"] == "system"
    assert kwargs["event_type"] == "upload_validation"
    payload = kwargs["payload"]
    assert payload["validation_result"] == "pass"
    assert payload["error"] is None
    assert len(payload["file_hash_sha256"]) == 64  # SHA-256 hex


def test_audit_recorded_on_fail(
    audited_validator: UploadValidator,
    mock_audit: MagicMock,
    empty_bytes: bytes,
) -> None:
    """Audit fires with validation_result='fail' even when validation raises."""
    with pytest.raises(CorruptOrEmptyError):
        audited_validator.validate(empty_bytes, "bad.pdf")
    mock_audit.record.assert_called_once()
    payload = mock_audit.record.call_args.kwargs["payload"]
    assert payload["validation_result"] == "fail"
    assert payload["error"] == "CorruptOrEmptyError"


def test_audit_failure_does_not_propagate(mock_audit: MagicMock, text_pdf_bytes: bytes) -> None:
    """Audit write exception is swallowed — caller sees ValidatedUpload, not audit error."""
    mock_audit.record.side_effect = RuntimeError("Supabase down")
    v = UploadValidator(audit_repo=mock_audit)
    result = v.validate(text_pdf_bytes, "lab.pdf")
    assert isinstance(result, ValidatedUpload)


def test_no_audit_repo_works(validator: UploadValidator, text_pdf_bytes: bytes) -> None:
    """audit_repo=None → validation succeeds without any audit call."""
    result = validator.validate(text_pdf_bytes, "lab.pdf")
    assert isinstance(result, ValidatedUpload)
