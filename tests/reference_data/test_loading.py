"""Tests for reference data loading — AC1, AC5, AC6."""

from src.reference_data import (
    load_all,
    load_condition_biomarker_map,
    load_guideline_ranges,
    load_loinc_subset,
    load_specialist_templates,
    load_taxonomy,
    load_ucum_units,
)


def test_load_all_returns_six_keys() -> None:
    data = load_all()
    assert set(data.keys()) == {
        "taxonomy",
        "loinc_subset",
        "ucum_units",
        "condition_biomarker_map",
        "specialist_templates",
        "guideline_ranges",
    }


def test_taxonomy_has_exactly_30_entries() -> None:
    # AC1: count of taxonomy entries is exactly 30
    taxonomy = load_taxonomy()
    assert len(taxonomy) == 30


def test_loinc_subset_loads() -> None:
    data = load_loinc_subset()
    assert "entries" in data
    assert len(data["entries"]) > 0


def test_ucum_units_loads() -> None:
    data = load_ucum_units()
    assert "units" in data
    assert "conversions" in data


def test_condition_biomarker_map_t2d_markers() -> None:
    # AC5: T2D lookup returns expected primary biomarkers
    data = load_condition_biomarker_map()
    t2d = data["conditions"]["T2D"]
    primary = t2d["primary_biomarkers"]
    monitoring = t2d["monitoring_biomarkers"]
    all_markers = set(primary) | set(monitoring)
    assert "hba1c" in all_markers
    assert "fasting_glucose" in all_markers
    assert "egfr" in all_markers
    # lipid markers
    assert "ldl_cholesterol" in all_markers or "total_cholesterol" in all_markers


def test_specialist_templates_cardiology_first_visit() -> None:
    # AC6: cardiology first_visit section list is present
    data = load_specialist_templates()
    template = data["templates"]["cardiology"]["first_visit"]
    assert "sections" in template
    section_ids = [s["id"] for s in template["sections"]]
    assert "lipid_panel" in section_ids
    assert "blood_pressure_trend" in section_ids
    assert "disclaimer" in section_ids


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
