"""Upload validator and ValidatedUpload model for the Vitalog ingestion pipeline.

UploadValidator is the entry point for all file uploads. It runs a 6-step
pipeline (empty → MIME → support → size → integrity → probes) and returns a
ValidatedUpload model on success. Every attempt writes an audit log entry.
"""

from __future__ import annotations

import hashlib
import io
import logging
from typing import Any

from pydantic import BaseModel, ConfigDict

from src.ingestion.errors import (
    CorruptOrEmptyError,
    FileTooLargeError,
    UnsupportedFormatError,
)

logger = logging.getLogger(__name__)

_MAX_BYTES_DEFAULT = 20 * 1024 * 1024  # 20 MB

# HEIC major-brand codes in the ISO Base Media File Format ftyp box.
# Bytes [4:8] == b"ftyp" is shared with MP4/M4A; the brand at [8:12] narrows it to HEIC/HEIF.
_HEIC_BRANDS: frozenset[bytes] = frozenset({b"heic", b"heix", b"hevc", b"hevx", b"mif1"})

_SUPPORTED_MIMES: frozenset[str] = frozenset(
    {"application/pdf", "image/jpeg", "image/png", "image/heic"}
)


class _Base(BaseModel):
    model_config = ConfigDict(strict=True)


class ValidatedUpload(_Base):
    """Output of a successful UploadValidator.validate() call."""

    file_bytes: bytes
    mime: str
    size_bytes: int
    is_text_extractable: bool | None  # None for images; True/False for PDFs
    resolution_warning: str | None  # None if adequate or N/A; warning string if <600×600


def _detect_mime(file_bytes: bytes) -> str:
    """Detect MIME type from file content (ignores client-supplied headers).

    HEIC check runs first because puremagic's HEIC database entry is unreliable
    across versions. The secondary brand check at bytes[8:12] prevents MP4/M4A
    (which share the ftyp box at bytes[4:8]) from being misidentified as HEIC.
    """
    import puremagic

    if len(file_bytes) >= 12 and file_bytes[4:8] == b"ftyp":
        if file_bytes[8:12] in _HEIC_BRANDS:
            return "image/heic"

    try:
        matches = puremagic.magic_string(file_bytes)
        if matches:
            return str(matches[0].mime_type)
    except Exception as _exc:  # noqa: BLE001
        logger.debug("puremagic MIME detection failed (falling back to octet-stream): %s", _exc)

    return "application/octet-stream"


class UploadValidator:
    """Validates uploaded file bytes and runs pre-LLM probes.

    Args:
        audit_repo: Optional AuditLogRepository. If provided, every call to
            validate() writes one audit entry regardless of pass/fail.
        max_bytes: File size cap in bytes. Defaults to 20 MB.
    """

    def __init__(
        self,
        audit_repo: Any | None = None,  # AuditLogRepository or None
        max_bytes: int = _MAX_BYTES_DEFAULT,
    ) -> None:
        self._audit = audit_repo
        self._max_bytes = max_bytes

    def validate(self, file_bytes: bytes, filename: str = "<unknown>") -> ValidatedUpload:
        """Validate file bytes and return a ValidatedUpload on success.

        The audit log entry is always written (try/except/finally pattern),
        including when an exception is raised.

        Raises:
            UnsupportedFormatError: MIME type not in supported set.
            FileTooLargeError: file exceeds the size cap.
            CorruptOrEmptyError: file is empty or content does not parse.
        """
        file_hash = hashlib.sha256(file_bytes).hexdigest()
        # Sanitise filename before storing in audit log: truncate and drop non-printable chars.
        safe_filename = filename[:255].encode("utf-8", errors="replace").decode("utf-8")
        result: ValidatedUpload | None = None
        error_name: str | None = None

        try:
            result = self._run_validation(file_bytes)
        except (UnsupportedFormatError, FileTooLargeError, CorruptOrEmptyError) as exc:
            error_name = type(exc).__name__
            raise
        finally:
            self._record_audit(
                file_hash=file_hash,
                filename=safe_filename,
                size_bytes=len(file_bytes),
                result=result,
                error_name=error_name,
            )

        return result

    # ── Private helpers ───────────────────────────────────────────────────────

    def _run_validation(self, file_bytes: bytes) -> ValidatedUpload:
        from src.ingestion.probes import probe_image, probe_pdf

        # Step 1: Empty check
        if len(file_bytes) == 0:
            raise CorruptOrEmptyError("file is 0 bytes")

        # Step 2: MIME detection
        mime = _detect_mime(file_bytes)

        # Step 3: MIME support check
        if mime not in _SUPPORTED_MIMES:
            raise UnsupportedFormatError(mime)

        # Step 4: Size check
        size = len(file_bytes)
        if size > self._max_bytes:
            raise FileTooLargeError(size, self._max_bytes)

        # Step 5: Content integrity
        self._check_integrity(file_bytes, mime)

        # Step 6: Probes
        is_text_extractable: bool | None = None
        resolution_warning: str | None = None

        if mime == "application/pdf":
            is_text_extractable = probe_pdf(file_bytes)
        else:
            try:
                resolution_warning = probe_image(file_bytes, mime)
            except ImportError as exc:
                raise UnsupportedFormatError(mime) from exc

        return ValidatedUpload(
            file_bytes=file_bytes,
            mime=mime,
            size_bytes=size,
            is_text_extractable=is_text_extractable,
            resolution_warning=resolution_warning,
        )

    def _check_integrity(self, file_bytes: bytes, mime: str) -> None:
        """Try to parse the file as its detected MIME type.

        Raises CorruptOrEmptyError if parsing fails (content doesn't match magic).
        """
        if mime == "application/pdf":
            try:
                import fitz

                doc = fitz.open(stream=file_bytes, filetype="pdf")
                doc.close()
            except Exception as exc:  # noqa: BLE001
                raise CorruptOrEmptyError(f"PDF cannot be opened: {exc}") from exc
        else:
            # Register HEIC opener before any Image.open() call on HEIC files.
            if mime == "image/heic":
                try:
                    import pillow_heif

                    pillow_heif.register_heif_opener()
                except ImportError as exc:
                    raise UnsupportedFormatError(mime) from exc

            try:
                from PIL import Image

                img = Image.open(io.BytesIO(file_bytes))
                img.verify()
            except Exception as exc:  # noqa: BLE001
                raise CorruptOrEmptyError(f"Image cannot be decoded: {exc}") from exc

    def _record_audit(
        self,
        file_hash: str,
        filename: str,
        size_bytes: int,
        result: ValidatedUpload | None,
        error_name: str | None,
    ) -> None:
        """Write audit log entry. Best-effort — never raises to the caller."""
        if self._audit is None:
            return

        payload: dict[str, Any] = {
            "file_hash_sha256": file_hash,
            "filename": filename,
            "size_bytes": size_bytes,
            "validation_result": "pass" if result is not None else "fail",
            "error": error_name,
            "mime": result.mime if result else None,
            "is_text_extractable": result.is_text_extractable if result else None,
            "resolution_warning": result.resolution_warning if result else None,
        }
        try:
            self._audit.record(
                actor="system",
                event_type="upload_validation",
                payload=payload,
            )
        except Exception:  # noqa: BLE001
            logger.warning("UploadValidator: audit log write failed (suppressed)")
