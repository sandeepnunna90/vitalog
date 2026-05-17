"""Typed exception hierarchy for the AI Gateway."""

from __future__ import annotations

from typing import Any


class GatewayError(Exception):
    """Base class for all gateway exceptions."""


class PromptNotFoundError(GatewayError):
    """Raised when prompt_id/version is not in the registry (before any network call)."""


class OutputValidationError(GatewayError):
    """Raised when the model output fails schema or citation validation."""


class ModelError(GatewayError):
    """Raised when the Anthropic adapter exhausts all retry attempts."""


class BannedPhraseViolation(GatewayError):  # noqa: N818
    """Raised when LLM output contains one or more banned clinical-advice phrases."""

    def __init__(self, phrases: list[str]) -> None:
        self.phrases = phrases
        super().__init__(f"Banned phrases detected in output: {phrases}")


class SchemaValidationError(GatewayError):
    """Raised when LLM output fails Pydantic schema validation; includes field-level diff."""

    def __init__(self, field_errors: list[Any]) -> None:
        self.field_errors = field_errors
        super().__init__(f"Schema validation failed: {field_errors}")


class ModeAVerificationError(GatewayError):
    """Raised when Mode A citation verification fails."""

    def __init__(self, reason: str, citation: object = None) -> None:
        self.reason = reason
        self.citation = citation
        super().__init__(f"Mode A verification failed: {reason}")


class OwnershipLeakError(ModeAVerificationError):
    """Raised when a citation references a record belonging to a different patient."""
