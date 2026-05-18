"""F4 — Context card composition from reference data only (no LLM).

Each card is assembled from three A2 files:
  - biomarker_taxonomy.json  (definition, conditions)
  - condition_biomarker_map.json  (display_name for relevance bullet)
  - guideline_ranges.json  (structured ranges with full citations)

Biomarkers not covered by guideline_ranges.json fall back to the simpler
taxonomy.guideline_ranges strings so every card still has cited ranges.
"""

from __future__ import annotations

from typing import Any

from src.intelligence.context_card_schemas import (
    CardNotAvailable,
    ContextCard,
    RangeWithCitation,
)
from src.reference_data import (
    load_condition_biomarker_map,
    load_guideline_ranges,
    load_taxonomy,
)

DISCLAIMER = (
    "Reference ranges are published guidelines, not personalized recommendations. "
    "Always discuss your results with your healthcare provider."
)


def get_context_card(
    vitalog_id: str,
    conditions: list[str],
) -> ContextCard | CardNotAvailable:
    """Return a context card for *vitalog_id* given the patient's *conditions*.

    Returns CardNotAvailable when the biomarker is not in the taxonomy.
    """
    entry = _find_taxonomy_entry(vitalog_id)
    if entry is None:
        return CardNotAvailable(vitalog_id=vitalog_id, reason="unknown-biomarker")

    relevance = _build_relevance(entry, conditions)
    ranges = _build_ranges_from_guideline_json(vitalog_id)
    if not ranges:
        ranges = _build_ranges_from_taxonomy(entry)

    return ContextCard(
        vitalog_id=vitalog_id,
        canonical_name=entry["canonical_name"],
        definition=entry["definition"],
        relevance=relevance,
        ranges_with_citations=ranges,
        disclaimer=DISCLAIMER,
    )


def _find_taxonomy_entry(vitalog_id: str) -> dict[str, Any] | None:
    for entry in load_taxonomy():
        if entry["vitalog_id"] == vitalog_id:
            return entry
    return None


def _build_relevance(entry: dict[str, Any], patient_conditions: list[str]) -> str:
    matched = [c for c in entry.get("conditions", []) if c in patient_conditions]
    if not matched:
        return "Not directly tied to your current conditions"
    cbm = load_condition_biomarker_map()["conditions"]
    display_names = [cbm[c]["display_name"] for c in matched if c in cbm]
    return (
        "Tracked for: " + ", ".join(display_names)
        if display_names
        else ("Not directly tied to your current conditions")
    )


def _build_ranges_from_guideline_json(vitalog_id: str) -> list[RangeWithCitation]:
    guidelines: dict[str, Any] = load_guideline_ranges()["guidelines"]
    ranges: list[RangeWithCitation] = []
    for g in guidelines.values():
        bio_ranges: dict[str, Any] | None = g["ranges"].get(vitalog_id)
        if bio_ranges is None:
            continue
        source_section: str | None = bio_ranges.get("source_section")
        doi = g.get("doi", "")
        full_citation = f"{g['citation']} {doi}".strip() if doi else g["citation"]
        for sub_key, sub_val in bio_ranges.items():
            if sub_key == "source_section":
                continue
            ranges.append(
                RangeWithCitation(
                    label=sub_val["label"],
                    value=sub_val["value"],
                    unit=sub_val["unit"],
                    source=full_citation,
                    source_section=source_section,
                )
            )
    return ranges


def _build_ranges_from_taxonomy(entry: dict[str, Any]) -> list[RangeWithCitation]:
    citations: dict[str, str] = entry.get("guideline_citations", {})
    first_citation = next(iter(citations.values()), "")
    ranges: list[RangeWithCitation] = []
    for key, val_str in entry.get("guideline_ranges", {}).items():
        label = key.replace("_", " ").title()
        ranges.append(
            RangeWithCitation(
                label=label,
                value=val_str,
                unit="",
                source=first_citation,
                source_section=None,
            )
        )
    return ranges
