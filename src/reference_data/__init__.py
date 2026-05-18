"""Reference data loader for Vitalog biomarker taxonomy and guideline ranges."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from src.reference_data.patient_profile import MARK_PATIENT_ID as MARK_PATIENT_ID
from src.reference_data.patient_profile import load_patient_profile as load_patient_profile
from src.reference_data.patient_profile_schemas import PatientProfile as PatientProfile

_DATA_DIR = Path(__file__).parent.parent.parent / "reference_data"

_REQUIRED_ENTRY_FIELDS = frozenset(
    {
        "vitalog_id",
        "canonical_name",
        "loinc_code",
        "ucum_unit",
        "unit_conversions",
        "aliases",
        "conditions",
        "guideline_ranges",
        "guideline_citations",
        "verification_tier",
        "verified",
    }
)


def _load_json(filename: str) -> Any:
    path = _DATA_DIR / filename
    with path.open(encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_taxonomy() -> list[dict[str, Any]]:
    """Load and return all 30 biomarker taxonomy entries (cached after first call)."""
    return _load_json("biomarker_taxonomy.json")  # type: ignore[no-any-return]


def load_loinc_subset() -> dict[str, Any]:
    """Load the LOINC code subset referenced by the taxonomy."""
    return _load_json("loinc_subset.json")  # type: ignore[no-any-return]


def load_ucum_units() -> dict[str, Any]:
    """Load UCUM unit definitions and conversion rules."""
    return _load_json("ucum_units.json")  # type: ignore[no-any-return]


@lru_cache(maxsize=1)
def load_condition_biomarker_map() -> dict[str, Any]:
    """Load the condition-to-biomarker mapping."""
    return _load_json("condition_biomarker_map.json")  # type: ignore[no-any-return]


def load_specialist_templates() -> dict[str, Any]:
    """Load specialist visit content section templates."""
    return _load_json("specialist_content_templates.json")  # type: ignore[no-any-return]


def load_guideline_ranges() -> dict[str, Any]:
    """Load published guideline ranges with citations."""
    return _load_json("guideline_ranges.json")  # type: ignore[no-any-return]


def load_all() -> dict[str, Any]:
    """Load and return all six reference data files as a single dict.

    This is the only public entry point that application services should use.
    Do not import JSON paths or individual loaders outside of this module.
    """
    return {
        "taxonomy": load_taxonomy(),
        "loinc_subset": load_loinc_subset(),
        "ucum_units": load_ucum_units(),
        "condition_biomarker_map": load_condition_biomarker_map(),
        "specialist_templates": load_specialist_templates(),
        "guideline_ranges": load_guideline_ranges(),
    }


def _build_alias_index(taxonomy: list[dict[str, Any]]) -> dict[str, str]:
    """Build a case-insensitive alias -> vitalog_id index from the taxonomy."""
    index: dict[str, str] = {}
    for entry in taxonomy:
        vid = entry["vitalog_id"]
        for alias in entry["aliases"]:
            index[alias.lower()] = vid
        index[entry["canonical_name"].lower()] = vid
        index[vid] = vid
    return index


@lru_cache(maxsize=1)
def _get_alias_index() -> dict[str, str]:
    return _build_alias_index(load_taxonomy())


def lookup_alias(raw_name: str) -> str | None:
    """Return the vitalog_id for a raw biomarker name, or None if not found.

    Matching is case-insensitive. Returns None for unrecognized names
    (caller should route to the pending taxonomy queue).
    """
    return _get_alias_index().get(raw_name.lower())


def lookup_guideline(vitalog_id: str) -> dict[str, Any] | None:
    """Return the guideline_ranges dict for a given vitalog_id, or None.

    Pulls directly from the taxonomy entry (not from guideline_ranges.json,
    which is the extended citation store for the Summary Generator).
    """
    for entry in load_taxonomy():
        if entry["vitalog_id"] == vitalog_id:
            result: dict[str, Any] = {
                "guideline_ranges": entry["guideline_ranges"],
                "guideline_citations": entry["guideline_citations"],
            }
            return result
    return None
