"""Typed exception hierarchy for the AI Gateway."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.gateway.citation_schemas import Citation


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

    def __init__(self, reason: str, citation: Citation | None = None) -> None:
        self.reason = reason
        self.citation = citation
        super().__init__(f"Mode A verification failed: {reason}")


class OwnershipLeakError(ModeAVerificationError):
    """Raised when a citation references a record belonging to a different patient.

    Kept as a distinct subclass (rather than a flag on ModeAVerificationError) so
    callers and tests can distinguish a security violation from a numeric mismatch
    without inspecting the reason string.
    """


class ModeBVerificationError(GatewayError):
    """Base class for Mode B prose verification failures."""


class UnmatchedNumericError(ModeBVerificationError):
    """Raised when a numeric value in prose has no matching record in the retrieval set."""

    def __init__(self, value: float, unit: str | None) -> None:
        self.value = value
        self.unit = unit
        super().__init__(f"Mode B: no retrieval-set match for value={value} unit={unit!r}")


class UnitMismatchError(ModeBVerificationError):
    """Raised when a numeric's adjacent unit does not match any value-matching record."""

    def __init__(self, value: float, cited_unit: str) -> None:
        self.value = value
        self.cited_unit = cited_unit
        super().__init__(f"Mode B: unit mismatch for value={value}, cited={cited_unit!r}")
