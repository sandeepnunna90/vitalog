"""Typed exception hierarchy for the Vitalog ingestion pipeline."""

from __future__ import annotations


class IngestionError(Exception):
    """Base class for all ingestion exceptions."""


class UnsupportedFormatError(IngestionError):
    """Raised when the uploaded file's MIME type is not in the supported set."""

    SUPPORTED: frozenset[str] = frozenset(
        {"application/pdf", "image/jpeg", "image/png", "image/heic"}
    )

    def __init__(self, detected_mime: str) -> None:
        self.detected_mime = detected_mime
        super().__init__(
            f"Unsupported format '{detected_mime}'. Supported formats: PDF, JPG/JPEG, PNG, HEIC."
        )


class FileTooLargeError(IngestionError):
    """Raised when the file exceeds the configured size cap."""

    def __init__(self, size_bytes: int, max_bytes: int) -> None:
        self.size_bytes = size_bytes
        self.max_bytes = max_bytes
        super().__init__(
            f"File is {size_bytes:,} bytes; "
            f"maximum allowed is {max_bytes:,} bytes ({max_bytes // (1024 * 1024)} MB)."
        )


class CorruptOrEmptyError(IngestionError):
    """Raised when the file is 0 bytes or its content does not match the detected MIME."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"File is corrupt or empty: {reason}")


class TextractFailureError(IngestionError):
    """Raised when AWS Textract fails after all retry attempts are exhausted."""

    def __init__(self, reason: str, attempt_count: int) -> None:
        self.reason = reason
        self.attempt_count = attempt_count
        super().__init__(f"Textract failed after {attempt_count} attempt(s): {reason}")
