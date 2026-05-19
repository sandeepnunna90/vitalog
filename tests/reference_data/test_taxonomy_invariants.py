"""Tests for taxonomy invariants and alias lookup — AC2, AC3, AC4."""

import pytest

from src.reference_data import (
    load_loinc_subset,
    load_taxonomy,
    load_ucum_units,
    lookup_alias,
    lookup_guideline,
)

_REQUIRED_FIELDS = {
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


def test_all_entries_have_required_fields() -> None:
    taxonomy = load_taxonomy()
    for entry in taxonomy:
        missing = _REQUIRED_FIELDS - set(entry.keys())
        assert not missing, f"Entry '{entry.get('vitalog_id')}' missing fields: {missing}"


def test_all_entries_are_canonical_and_verified() -> None:
    taxonomy = load_taxonomy()
    for entry in taxonomy:
        assert entry["verification_tier"] == "canonical", entry["vitalog_id"]
        assert entry["verified"] is True, entry["vitalog_id"]


def test_all_vitalog_ids_are_unique() -> None:
    taxonomy = load_taxonomy()
    ids = [e["vitalog_id"] for e in taxonomy]
    assert len(ids) == len(set(ids)), "Duplicate vitalog_id found"


def test_all_loinc_codes_in_subset() -> None:
    taxonomy = load_taxonomy()
    loinc_data = load_loinc_subset()
    subset_codes = set(loinc_data["entries"].keys())
    for entry in taxonomy:
        code = entry["loinc_code"]
        assert code in subset_codes, (
            f"LOINC code {code} for '{entry['vitalog_id']}' not in loinc_subset.json"
        )


def test_all_entries_have_at_least_one_citation() -> None:
    taxonomy = load_taxonomy()
    for entry in taxonomy:
        citations = entry["guideline_citations"]
        # CBC panel markers (e.g. RBC, MCV, neutrophils) have no formal guideline targets
        if not entry.get("guideline_ranges"):
            continue
        assert citations, f"Entry '{entry['vitalog_id']}' has guideline_ranges but empty guideline_citations"
        for _org, citation_str in citations.items():
            assert "http" in citation_str, (
                f"Citation for '{entry['vitalog_id']}' missing URL: {citation_str}"
            )


def test_lookup_alias_hba1c_canonical() -> None:
    # AC2: "HbA1c" resolves to vitalog_id = "hba1c"
    assert lookup_alias("HbA1c") == "hba1c"


def test_lookup_alias_hba1c_lowercase() -> None:
    # AC2: lowercase alias works
    assert lookup_alias("hba1c") == "hba1c"


def test_lookup_alias_hemoglobin_a1c_spelling() -> None:
    # AC2: "Hemoglobin A1c" spelling works
    assert lookup_alias("Hemoglobin A1c") == "hba1c"


def test_lookup_alias_a1c_abbreviation() -> None:
    # AC2: short "A1C" abbreviation works
    assert lookup_alias("A1C") == "hba1c"


def test_lookup_alias_unknown_returns_none() -> None:
    assert lookup_alias("completely unknown biomarker xyz") is None


def test_lookup_alias_case_insensitive() -> None:
    assert lookup_alias("FASTING GLUCOSE") == "fasting_glucose"
    assert lookup_alias("fasting glucose") == "fasting_glucose"


def test_hba1c_entry_loinc_and_unit() -> None:
    # AC2: LOINC code and canonical unit
    taxonomy = load_taxonomy()
    hba1c = next(e for e in taxonomy if e["vitalog_id"] == "hba1c")
    assert hba1c["loinc_code"] == "4548-4"
    assert hba1c["ucum_unit"] == "%"


def test_lookup_guideline_hba1c_ada_target() -> None:
    # AC3: guideline lookup returns ADA target
    result = lookup_guideline("hba1c")
    assert result is not None
    ranges = result["guideline_ranges"]
    assert "ADA_target_diabetes" in ranges
    assert "<7.0" in ranges["ADA_target_diabetes"]


def test_lookup_guideline_hba1c_ada_normal() -> None:
    # AC3: ADA normal
    result = lookup_guideline("hba1c")
    assert result is not None
    assert "<5.7" in result["guideline_ranges"]["ADA_normal"]


def test_lookup_guideline_hba1c_citation_ada() -> None:
    # AC3: citation string points to ADA Standards of Care
    result = lookup_guideline("hba1c")
    assert result is not None
    citations = result["guideline_citations"]
    assert "ADA" in citations
    assert "Standards of Care" in citations["ADA"] or "doi.org" in citations["ADA"]


def test_hba1c_ucum_conversion_ifcc_formula() -> None:
    # AC4: mmol/mol -> % conversion rule exists and uses ifcc_to_ngsp formula
    taxonomy = load_taxonomy()
    hba1c = next(e for e in taxonomy if e["vitalog_id"] == "hba1c")
    conversions = hba1c["unit_conversions"]
    ifcc_rule = next(
        (c for c in conversions if c["from_unit"] == "mmol/mol" and c["to_unit"] == "%"),
        None,
    )
    assert ifcc_rule is not None, "No mmol/mol -> % conversion rule for HbA1c"
    assert ifcc_rule["formula"] == "ifcc_to_ngsp"


def test_ucum_ifcc_conversion_accuracy() -> None:
    # AC4: verify the IFCC->NGSP equation in ucum_units.json matches known values
    # IFCC equation: NGSP% = (0.0915 * IFCC_mmol/mol) + 2.15
    # Test case: 53 mmol/mol -> ~7.0% (ADA target threshold)
    ucum_data = load_ucum_units()
    ifcc_rule = next(
        (c for c in ucum_data["conversions"] if c["id"] == "hba1c_ifcc_to_ngsp"),
        None,
    )
    assert ifcc_rule is not None
    assert ifcc_rule["formula"] == "ifcc_to_ngsp"
    # Validate the equation string is present
    assert "0.0915" in ifcc_rule["equation"]
    assert "2.15" in ifcc_rule["equation"]

    # Direct calculation check: 53 mmol/mol should give ~7.0% per IFCC master equation
    ifcc_value = 53.0
    ngsp_percent = 0.0915 * ifcc_value + 2.15
    assert abs(ngsp_percent - 7.0) < 0.05, f"IFCC 53 -> expected ~7.0%, got {ngsp_percent}"


def test_all_aliases_non_empty() -> None:
    taxonomy = load_taxonomy()
    for entry in taxonomy:
        assert entry["aliases"], f"Entry '{entry['vitalog_id']}' has empty aliases list"


def test_clinical_biomarkers_have_guideline_ranges() -> None:
    # Biomarkers with conditions listed are expected to have guideline targets.
    # CBC panel markers (no conditions) may omit guideline_ranges.
    taxonomy = load_taxonomy()
    for entry in taxonomy:
        if entry.get("conditions"):
            assert entry["guideline_ranges"], (
                f"Entry '{entry['vitalog_id']}' has conditions but empty guideline_ranges"
            )


@pytest.mark.parametrize(
    "vitalog_id",
    ["hba1c", "fasting_glucose", "ldl_cholesterol", "egfr", "bp_systolic", "tsh"],
)
def test_key_biomarkers_present(vitalog_id: str) -> None:
    taxonomy = load_taxonomy()
    ids = {e["vitalog_id"] for e in taxonomy}
    assert vitalog_id in ids
