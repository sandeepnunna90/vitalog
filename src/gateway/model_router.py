"""Model routing table for the AI Gateway.

Capstone: single-provider (Anthropic, claude-sonnet-4-6) for all tasks.
v1 adds a Task enum and per-task routing so multi-provider is additive here.
"""

from __future__ import annotations

_DEFAULT_MODEL = "claude-sonnet-4-6"


def default_model() -> str:
    """Return the default model ID for all tasks (capstone: single-provider)."""
    return _DEFAULT_MODEL
