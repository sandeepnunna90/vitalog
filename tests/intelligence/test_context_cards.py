"""Unit tests for F4 context card composition (AC1–AC6)."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.intelligence.context_card_schemas import CardNotAvailable, ContextCard
from src.intelligence.context_cards import DISCLAIMER, get_context_card
from src.reference_data import load_condition_biomarker_map, load_taxonomy

MARK_CONDITIONS = ["T2D", "HTN", "hypothyroidism"]

ALL_VITALOG_IDS = [
    "hba1c",
    "fasting_glucose",
    "postprandial_glucose",
    "total_cholesterol",
    "ldl_cholesterol",
    "hdl_cholesterol",
    "triglycerides",
    "non_hdl_cholesterol",
    "egfr",
    "creatinine",
    "urine_acr",
    "bp_systolic",
    "bp_diastolic",
    "tsh",
    "free_t4",
    "alt",
    "ast",
    "hs_crp",
    "vitamin_d",
    "vitamin_b12",
    "ferritin",
    "hemoglobin",
    "wbc",
    "platelets",
    "sodium",
    "potassium",
    "chloride",
    "bun",
    "serum_glucose",
    "fructosamine",
]


def _hba1c_card() -> ContextCard:
    result = get_context_card("hba1c", MARK_CONDITIONS)
    assert isinstance(result, ContextCard)
    return result


# AC1 — HbA1c card returns ContextCard for T2D patient
def test_hba1c_returns_context_card() -> None:
    card = get_context_card("hba1c", MARK_CONDITIONS)
    assert isinstance(card, ContextCard)


# AC1 — definition is populated
def test_hba1c_definition_non_empty() -> None:
    card = _hba1c_card()
    assert card.definition and len(card.definition) > 10


# AC3 — every range carries a non-empty source citation
def test_hba1c_every_range_has_source() -> None:
    card = _hba1c_card()
    assert card.ranges_with_citations, "Expected at least one range"
    for r in card.ranges_with_citations:
        assert r.source, f"Range '{r.label}' has empty source"


# AC1 — relevance mentions the matched condition display name
def test_hba1c_relevance_contains_t2d_display_name() -> None:
    card = _hba1c_card()
    assert "Type 2 Diabetes" in card.relevance


# AC2 — biomarker not tied to patient conditions → generic relevance
def test_ldl_no_matching_conditions_relevance() -> None:
    # LDL conditions are CVD/dyslipidemia/T2D/HTN — patient has T2D and HTN,
    # so they DO match. Use a patient with no matching conditions.
    card = get_context_card("ldl_cholesterol", ["hypothyroidism"])
    assert isinstance(card, ContextCard)
    assert card.relevance == "Not directly tied to your current conditions"


# AC5 — unknown vitalog_id → CardNotAvailable
def test_unknown_biomarker_returns_not_available() -> None:
    result = get_context_card("unknown_xyzzy", MARK_CONDITIONS)
    assert isinstance(result, CardNotAvailable)
    assert result.reason == "unknown-biomarker"
    assert result.vitalog_id == "unknown_xyzzy"


# AC4 — no anthropic or Gateway import in context_cards.py
def test_no_anthropic_or_gateway_in_source() -> None:
    src_path = Path(__file__).parent.parent.parent / "src" / "intelligence" / "context_cards.py"
    src = src_path.read_text()
    assert "anthropic" not in src
    assert "Gateway" not in src


# AC6 — all 30 taxonomy biomarkers return a ContextCard
@pytest.mark.parametrize("vitalog_id", ALL_VITALOG_IDS)
def test_all_taxonomy_ids_return_context_card(vitalog_id: str) -> None:
    result = get_context_card(vitalog_id, MARK_CONDITIONS)
    assert isinstance(result, ContextCard), (
        f"{vitalog_id} returned {type(result).__name__} instead of ContextCard"
    )


# AC6 — every returned card has the disclaimer
@pytest.mark.parametrize("vitalog_id", ALL_VITALOG_IDS)
def test_all_cards_have_disclaimer(vitalog_id: str) -> None:
    result = get_context_card(vitalog_id, MARK_CONDITIONS)
    assert isinstance(result, ContextCard)
    assert result.disclaimer == DISCLAIMER


# AC3 — every card (all 30, including fallback-path biomarkers) has non-empty cited ranges
@pytest.mark.parametrize("vitalog_id", ALL_VITALOG_IDS)
def test_all_cards_have_cited_ranges(vitalog_id: str) -> None:
    result = get_context_card(vitalog_id, MARK_CONDITIONS)
    assert isinstance(result, ContextCard)
    assert result.ranges_with_citations, f"{vitalog_id}: expected at least one range"
    for r in result.ranges_with_citations:
        assert r.source, f"{vitalog_id}: range '{r.label}' has empty source citation"


# Data integrity — any condition code that IS in cbm must have a display_name.
# taxonomy.conditions is intentionally broader than cbm (9 capstone conditions); codes
# outside cbm are silently skipped in _build_relevance by design. This test guards the
# narrower invariant: codes that DO appear in cbm are well-formed.
def test_cbm_conditions_have_display_names() -> None:
    cbm = load_condition_biomarker_map()["conditions"]
    for code, entry in cbm.items():
        assert "display_name" in entry and entry["display_name"], (
            f"condition_biomarker_map entry '{code}' is missing a display_name"
        )


# Data integrity — biomarkers whose taxonomy.conditions intersect cbm resolve display names.
# Guards: if a patient condition matches a taxonomy condition AND that code is in cbm,
# _build_relevance will always produce a non-empty display name.
def test_taxonomy_cbm_intersection_always_has_display_name() -> None:
    cbm = load_condition_biomarker_map()["conditions"]
    for entry in load_taxonomy():
        for code in entry.get("conditions", []):
            if code in cbm:
                assert "display_name" in cbm[code] and cbm[code]["display_name"], (
                    f"vitalog_id '{entry['vitalog_id']}': condition '{code}' is in cbm "
                    "but has no display_name — _build_relevance would silently degrade"
                )
