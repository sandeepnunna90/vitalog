"""Tests for reference data loading — AC1, AC5, AC6."""

from src.reference_data import (
    load_all,
    load_biomarker_groups,
    load_guideline_ranges,
    load_loinc_subset,
    load_taxonomy,
    load_ucum_units,
)


def test_load_all_returns_expected_keys() -> None:
    data = load_all()
    assert set(data.keys()) == {
        "taxonomy",
        "loinc_subset",
        "ucum_units",
        "biomarker_groups",
        "guideline_ranges",
    }


def test_taxonomy_has_at_least_30_entries() -> None:
    # AC1: original seed was 30; CBC panel expansion added 18 more
    taxonomy = load_taxonomy()
    assert len(taxonomy) >= 30


def test_loinc_subset_loads() -> None:
    data = load_loinc_subset()
    assert "entries" in data
    assert len(data["entries"]) > 0


def test_ucum_units_loads() -> None:
    data = load_ucum_units()
    assert "units" in data
    assert "conversions" in data


def test_biomarker_groups_t2d_markers() -> None:
    # AC5: T2D lookup returns expected biomarkers
    data = load_biomarker_groups()
    t2d = data["conditions"]["T2D"]
    markers = set(t2d["biomarkers"])
    assert "hba1c" in markers
    assert "fasting_glucose" in markers
    assert "egfr" in markers
    assert "ldl_cholesterol" in markers or "total_cholesterol" in markers


def test_guideline_ranges_loads_all_organizations() -> None:
    data = load_guideline_ranges()
    assert "guidelines" in data
    guids = data["guidelines"]
    assert "ADA_2024" in guids
    assert "ACC_AHA_CHOLESTEROL_2018" in guids
    assert "ACC_AHA_HTN_2017" in guids
    assert "ATA_2014" in guids
    assert "KDIGO_2024" in guids


def test_load_all_no_exceptions() -> None:
    # AC1 smoke test: load_all() must not raise
    result = load_all()
    assert result["taxonomy"] is not None
