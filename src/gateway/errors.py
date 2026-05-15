"""Typed exception hierarchy for the AI Gateway."""

from __future__ import annotations


class GatewayError(Exception):
    """Base class for all gateway exceptions."""


class PromptNotFoundError(GatewayError):
    """Raised when prompt_id/version is not in the registry (before any network call)."""


class OutputValidationError(GatewayError):
    """Raised when the model output fails schema or citation validation."""


class ModelError(GatewayError):
    """Raised when the Anthropic adapter exhausts all retry attempts."""
