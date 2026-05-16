"""Builds the alias → vitalog_id index for Tier 1 normalization."""

from __future__ import annotations

import re
from typing import Any


def _normalize_key(raw: str) -> str:
    """Lowercase + collapse whitespace + strip parenthetical descriptors.

    Examples:
        "HbA1c (glycated hemoglobin)" → "hba1c"
        "  Hemoglobin   A1c  "        → "hemoglobin a1c"
    """
    raw = re.sub(r"\s*\(.*?\)", "", raw)
    return " ".join(raw.split()).lower()


def build_index(taxonomy: list[dict[str, Any]]) -> dict[str, str]:
    """Return alias → vitalog_id map for every entry in the taxonomy.

    Raises ValueError if two different entries share an alias after normalization —
    that is a curation bug, not a runtime condition.
    """
    index: dict[str, str] = {}
    for entry in taxonomy:
        vid: str = entry["vitalog_id"]
        candidates: list[str] = [entry["canonical_name"], vid] + list(entry["aliases"])
        for raw in candidates:
            key = _normalize_key(raw)
            if not key:
                continue
            if key in index and index[key] != vid:
                raise ValueError(f"Duplicate alias {raw!r} maps to both {index[key]!r} and {vid!r}")
            index[key] = vid
    return index
