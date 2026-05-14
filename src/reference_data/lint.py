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

# Must stay in sync with _REQUIRED_ENTRY_FIELDS in __init__.py
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


def _check_taxonomy(errors: list[str]) -> None:
    def err(msg: str) -> None:
        errors.append(msg)
        print(f"  ERROR: {msg}", file=sys.stderr)

    print("Checking biomarker_taxonomy.json...")
    taxonomy = load_taxonomy()
    loinc_subset = load_loinc_subset()
    subset_codes = set(loinc_subset["entries"].keys())
    seen_ids: set[str] = set()

    for entry in taxonomy:
        vid = entry.get("vitalog_id", "<unknown>")

        missing = _REQUIRED_ENTRY_FIELDS - set(entry.keys())
        if missing:
            err(f"[{vid}] missing required fields: {missing}")

        if vid in seen_ids:
            err(f"[{vid}] duplicate vitalog_id")
        seen_ids.add(str(vid))

        if entry.get("verification_tier") != "canonical":
            err(f"[{vid}] verification_tier must be 'canonical'")
        if not entry.get("verified"):
            err(f"[{vid}] verified must be True")

        loinc = entry.get("loinc_code", "")
        if loinc not in subset_codes:
            err(f"[{vid}] LOINC code '{loinc}' not found in loinc_subset.json")

        citations = entry.get("guideline_citations", {})
        if not citations:
            err(f"[{vid}] guideline_citations is empty")
        for org, citation_str in citations.items():
            if "http" not in str(citation_str):
                err(f"[{vid}] citation for '{org}' missing URL")

        if not entry.get("aliases"):
            err(f"[{vid}] aliases list is empty")
        if not entry.get("guideline_ranges"):
            err(f"[{vid}] guideline_ranges is empty")

    expected_count = 30  # update together with test_taxonomy_has_exactly_30_entries
    if len(taxonomy) != expected_count:
        err(f"taxonomy has {len(taxonomy)} entries; expected exactly {expected_count}")

    print(f"  {len(taxonomy)} entries checked.")


def main() -> None:
    print("Running Vitalog reference data invariant linter...")
    errors: list[str] = []
    _check_taxonomy(errors)

    if errors:
        print(f"\nLint FAILED — {len(errors)} error(s) found.", file=sys.stderr)
        sys.exit(1)
    else:
        print("\nLint PASSED — all invariants satisfied.")


if __name__ == "__main__":
    main()
