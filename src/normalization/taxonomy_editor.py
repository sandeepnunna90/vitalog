"""Audited editor for biomarker_taxonomy.json — only legitimate path to modify aliases."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.normalization.tier1 import _index

_DEFAULT_TAXONOMY_PATH = (
    Path(__file__).parent.parent.parent / "reference_data" / "biomarker_taxonomy.json"
)


def add_alias(
    vitalog_id: str,
    alias: str,
    taxonomy_path: Path = _DEFAULT_TAXONOMY_PATH,
) -> None:
    """Append alias to the given vitalog_id entry and rebuild the Tier 1 index.

    Raises ValueError if vitalog_id is not found or alias already exists on any entry.
    """
    taxonomy: list[dict[str, Any]] = json.loads(taxonomy_path.read_text(encoding="utf-8"))

    target = next((e for e in taxonomy if e["vitalog_id"] == vitalog_id), None)
    if target is None:
        raise ValueError(f"vitalog_id {vitalog_id!r} not found in taxonomy")

    normalised = alias.strip().lower()
    for entry in taxonomy:
        existing = [a.strip().lower() for a in entry["aliases"]]
        if normalised in existing or entry["canonical_name"].strip().lower() == normalised:
            raise ValueError(f"Alias {alias!r} already exists on entry {entry['vitalog_id']!r}")

    target["aliases"].append(alias)
    taxonomy_path.write_text(
        json.dumps(taxonomy, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    # Invalidate the cached index so the next lookup rebuilds from the updated file
    _index.cache_clear()
