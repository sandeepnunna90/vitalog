"""Unit tests for Tier 1 alias lookup (E1)."""

from __future__ import annotations

import pytest

from src.normalization.index_builder import _normalize_key, build_index
from src.normalization.tier1 import lookup
from src.reference_data import load_taxonomy

_TAXONOMY = load_taxonomy()

# ── _normalize_key ────────────────────────────────────────────────────────────


def test_normalize_lowercases() -> None:
    assert _normalize_key("HbA1c") == "hba1c"


def test_normalize_collapses_whitespace() -> None:
    assert _normalize_key("  Hemoglobin   A1c  ") == "hemoglobin a1c"


def test_normalize_strips_parenthetical() -> None:
    assert _normalize_key("HbA1c (glycated hemoglobin)") == "hba1c"


def test_normalize_strips_mid_parenthetical() -> None:
    assert _normalize_key("Vitamin D (25-OH)") == "vitamin d"


def test_normalize_empty_string() -> None:
    assert _normalize_key("") == ""


# ── Multi-alias resolution (AC1, AC2) ────────────────────────────────────────


def test_lookup_hba1c_primary_alias() -> None:
    assert lookup("HbA1c") == "hba1c"


def test_lookup_hba1c_all_aliases() -> None:
    aliases = ["Hemoglobin A1c", "A1C", "glycated hemoglobin", "glycosylated hemoglobin"]
    for alias in aliases:
        assert lookup(alias) == "hba1c", f"Expected hba1c for {alias!r}"


def test_lookup_ldl_aliases() -> None:
    for alias in ["LDL", "LDL-C", "LDL cholesterol", "ldl cholesterol"]:
        assert lookup(alias) == "ldl_cholesterol", f"Failed for {alias!r}"


# ── Unknown returns None (AC3) ────────────────────────────────────────────────


def test_lookup_unknown_returns_none() -> None:
    assert lookup("XYZ123_not_a_biomarker") is None


def test_lookup_empty_string_returns_none() -> None:
    assert lookup("") is None


def test_lookup_partial_name_returns_none() -> None:
    assert lookup("Hemo") is None


# ── Case folding (AC4) ────────────────────────────────────────────────────────


def test_lookup_case_insensitive() -> None:
    assert lookup("HBA1C") == "hba1c"
    assert lookup("hba1c") == "hba1c"
    assert lookup("HbA1c") == "hba1c"


def test_lookup_mixed_case_ldl() -> None:
    assert lookup("LDL CHOLESTEROL") == "ldl_cholesterol"


# ── Whitespace normalization (implementation note) ────────────────────────────


def test_lookup_extra_whitespace() -> None:
    assert lookup("  Hemoglobin   A1c  ") == "hba1c"


# ── Parenthetical stripping (implementation note) ─────────────────────────────


def test_lookup_with_parenthetical() -> None:
    assert lookup("HbA1c (glycated hemoglobin)") == "hba1c"


# ── All 30 canonical names resolve (parametrized) ────────────────────────────


@pytest.mark.parametrize(
    "entry",
    _TAXONOMY,
    ids=[e["vitalog_id"] for e in _TAXONOMY],
)
def test_canonical_name_resolves(entry: dict) -> None:  # type: ignore[type-arg]
    vid = entry["vitalog_id"]
    assert lookup(entry["canonical_name"]) == vid


@pytest.mark.parametrize(
    "entry",
    _TAXONOMY,
    ids=[e["vitalog_id"] for e in _TAXONOMY],
)
def test_vitalog_id_resolves_to_itself(entry: dict) -> None:  # type: ignore[type-arg]
    vid = entry["vitalog_id"]
    assert lookup(vid) == vid


# ── All aliases in taxonomy resolve (parametrized) ───────────────────────────


def _alias_params() -> list[tuple[str, str]]:
    return [(alias, entry["vitalog_id"]) for entry in _TAXONOMY for alias in entry["aliases"]]


@pytest.mark.parametrize("alias,expected_vid", _alias_params())
def test_alias_resolves(alias: str, expected_vid: str) -> None:
    assert lookup(alias) == expected_vid, f"Alias {alias!r} → expected {expected_vid!r}"


# ── Duplicate alias detection (build_index) ───────────────────────────────────


def test_build_index_raises_on_duplicate_alias() -> None:
    taxonomy: list[dict] = [  # type: ignore[type-arg]
        {"vitalog_id": "a", "canonical_name": "Alpha", "aliases": ["shared"]},
        {"vitalog_id": "b", "canonical_name": "Beta", "aliases": ["shared"]},
    ]
    with pytest.raises(ValueError, match="Duplicate alias"):
        build_index(taxonomy)


def test_build_index_same_alias_same_vid_is_ok() -> None:
    taxonomy: list[dict] = [  # type: ignore[type-arg]
        {"vitalog_id": "a", "canonical_name": "Alpha", "aliases": ["alpha", "Alpha"]},
    ]
    index = build_index(taxonomy)
    assert index["alpha"] == "a"


# ── Lookup stability (AC6 — O(1), deterministic) ─────────────────────────────


def test_repeated_lookups_are_stable() -> None:
    """Same input always returns the same vitalog_id across repeated calls."""
    for _ in range(5):
        assert lookup("HbA1c") == "hba1c"
        assert lookup("XYZ_unknown_999") is None
