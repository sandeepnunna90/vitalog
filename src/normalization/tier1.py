"""Tier 1 normalization — O(1) alias lookup backed by the 30-entry taxonomy."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from src.normalization.index_builder import _normalize_key, build_index
from src.reference_data import load_taxonomy


@lru_cache(maxsize=1)
def _index() -> dict[str, str]:
    taxonomy: list[dict[str, Any]] = load_taxonomy()
    return build_index(taxonomy)


def lookup(raw_name: str) -> str | None:
    """Return vitalog_id for raw_name, or None if not in the Tier 1 index.

    Matching is case-insensitive, whitespace-collapsed, and strips parenthetical
    descriptors. A None result means the caller should route to the E2 pending queue.
    """
    return _index().get(_normalize_key(raw_name))
