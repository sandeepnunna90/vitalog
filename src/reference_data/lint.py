"""Invariant linter for reference data files.

Run via: python -m src.reference_data.lint
Exits non-zero if any invariant is violated.
"""

from __future__ import annotations

import sys

from src.reference_data import (
    load_loinc_subset,
    load_taxonomy,
)

_REQUIRED_ENTRY_FIELDS = {
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

_ERRORS: list[str] = []


def _err(msg: str) -> None:
    _ERRORS.append(msg)
    print(f"  ERROR: {msg}", file=sys.stderr)


def _check_taxonomy() -> None:
    print("Checking biomarker_taxonomy.json...")
    taxonomy = load_taxonomy()
    loinc_subset = load_loinc_subset()
    subset_codes = set(loinc_subset["entries"].keys())
    seen_ids: set[str] = set()

    for entry in taxonomy:
        vid = entry.get("vitalog_id", "<unknown>")

        missing = _REQUIRED_ENTRY_FIELDS - set(entry.keys())
        if missing:
            _err(f"[{vid}] missing required fields: {missing}")

        if vid in seen_ids:
            _err(f"[{vid}] duplicate vitalog_id")
        seen_ids.add(vid)

        if entry.get("verification_tier") != "canonical":
            _err(f"[{vid}] verification_tier must be 'canonical'")
        if not entry.get("verified"):
            _err(f"[{vid}] verified must be True")

        loinc = entry.get("loinc_code", "")
        if loinc not in subset_codes:
            _err(f"[{vid}] LOINC code '{loinc}' not found in loinc_subset.json")

        citations = entry.get("guideline_citations", {})
        if not citations:
            _err(f"[{vid}] guideline_citations is empty")
        for org, citation_str in citations.items():
            if "http" not in str(citation_str):
                _err(f"[{vid}] citation for '{org}' missing URL")

        if not entry.get("aliases"):
            _err(f"[{vid}] aliases list is empty")
        if not entry.get("guideline_ranges"):
            _err(f"[{vid}] guideline_ranges is empty")

    expected_count = 30
    if len(taxonomy) != expected_count:
        _err(f"taxonomy has {len(taxonomy)} entries; expected exactly {expected_count}")

    print(f"  {len(taxonomy)} entries checked.")


def main() -> None:
    print("Running Vitalog reference data invariant linter...")
    _check_taxonomy()

    if _ERRORS:
        print(f"\nLint FAILED — {len(_ERRORS)} error(s) found.", file=sys.stderr)
        sys.exit(1)
    else:
        print("\nLint PASSED — all invariants satisfied.")


if __name__ == "__main__":
    main()
