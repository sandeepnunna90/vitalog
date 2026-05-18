# F4 — Context cards

**Epic:** Intelligence
**Points:** 3
**Priority:** Medium
**Depends on:** A2, F1
**Architecture refs:** PRD v2 Trend View "Context cards" row

## User story

As Mark seeing a biomarker name in my trend view,
I want a plain-language context card explaining what HbA1c is, why it matters for my conditions, and what the published target range is (with citation),
So that I can understand my chart without leaving the app and without being told what to do.

## Why this matters

Context cards turn "a number on a chart" into "a number I understand". They're entirely composed from reference data — no LLM, no hallucination risk. The citation discipline (every range with a published source) is what keeps Vitalog out of unauthorized clinical content.

## Acceptance criteria

1. **Given** a `vitalog_id="hba1c"` and Mark's patient profile (T2D), **When** I call `ContextCard.get(vitalog_id, patient_id)`, **Then** I get: plain-language definition (from taxonomy), condition-relevance bullet (from condition→biomarker map), the most-specific applicable guideline range (from guideline_ranges), and the published-source citation.
2. **Given** a biomarker not mapped to any of Mark's conditions, **When** the card is composed, **Then** the relevance bullet says "Not directly tied to your current conditions" rather than fabricating a connection.
3. **Given** the card output, **When** I inspect it, **Then** EVERY range bound carries a `source` field (e.g., `"ADA Standards of Care 2024 §6"`) — never a free-floating number.
4. **Given** the contract, **When** I `grep "anthropic\|Gateway" src/intelligence/context_cards.py`, **Then** I find ZERO matches (pure deterministic lookups).
5. **Given** a biomarker with no canonical entry (Tier 4 pending), **When** I request a card, **Then** I get a typed `CardNotAvailable` response, NOT a partially-fabricated card.
6. **Given** the card response, **When** the MCP tool returns it, **Then** the structure is stable Pydantic (definition, relevance, ranges_with_citations, disclaimer).

## Files to create / modify

- `src/intelligence/context_cards.py`
- `src/intelligence/context_card_schemas.py` — `ContextCard` Pydantic model
- `tests/intelligence/test_context_cards.py`
- `reference_data/biomarker_taxonomy.json` — confirm every entry has `definition` field (extend A2 if missing)

## Implementation notes

- This is the "use reference data correctly" story. All content is composed from `biomarker_taxonomy.json` + `condition_biomarker_map.json` + `guideline_ranges.json` (all from A2).
- The disclaimer string is embedded in every card: "Reference ranges are published guidelines, not personalized recommendations. Always discuss your results with your healthcare provider."
- For biomarkers with multiple applicable guideline ranges (e.g., LDL-C has separate ACC/AHA targets for primary vs secondary prevention), the card returns all of them as a list with each tagged by its applicability.
- The card knows the patient's conditions but does NOT make claims about what they mean for the patient — it just shows the guidelines and lets the user read.

## Verification

- `pytest tests/intelligence/test_context_cards.py -q` — covers every taxonomy entry
- Manual: render cards for HbA1c, LDL-C, eGFR, BP — eyeball-check that citations are intact

## INVEST check

- [x] Independent — only A2 + F1 (for the relevance lookup) required
- [x] Negotiable — exact card layout flexible
- [x] Valuable — supports trend understanding
- [x] Estimable — well-bounded
- [x] Small — 3 pts
- [x] Testable — easy to fixture

## Deferred (explicitly out of this story)

- Personalized phrasing per patient — v1+
- "What changed since last reading" deltas in the card — v1
- Image / icon assets — v1 web UI

## Notes / changelog

### Implementation (2026-05-18)

**Files created:**
- `reference_data/biomarker_taxonomy.json` — added `definition` field to all 30 entries (was missing; plain-language 1–2 sentence descriptions inserted after `canonical_name`)
- `src/intelligence/context_card_schemas.py` — `RangeWithCitation`, `ContextCard`, `CardNotAvailable` Pydantic v2 models with `ConfigDict(strict=True)`
- `src/intelligence/context_cards.py` — `get_context_card(vitalog_id, conditions)` pure function; two-tier range lookup (primary: `guideline_ranges.json` rich structured data; fallback: `taxonomy.guideline_ranges` simple strings with taxonomy citations); `DISCLAIMER` constant
- `tests/intelligence/test_context_cards.py` — 99 unit tests covering all ACs

**Key design decisions:**
- **Two-tier range source:** 16 biomarkers appear in `guideline_ranges.json` (rich `label/value/unit/source_section` structure with DOI citations); 14 fall back to `taxonomy.guideline_ranges` simple strings — every card always has at least one cited range (AC3)
- **Relevance bullet:** intersects `taxonomy.conditions` with caller-supplied patient conditions; looks up `display_name` from `condition_biomarker_map.json`. `taxonomy.conditions` is intentionally broader than the 9 capstone cbm conditions — out-of-scope codes (NAFLD, anemia, hyperthyroidism, etc.) are silently skipped by design
- **No LLM:** zero `anthropic`/`Gateway` imports; enforced by source-scan test (AC4)
- **Data-integrity tests:** two new tests guard that all cbm entries have `display_name` and that any condition code in both taxonomy and cbm always resolves correctly

**PR review fixes:**
- Added `test_all_cards_have_cited_ranges` — parametrized across all 30 IDs, asserts `r.source != ""` for every range (closes AC3 gap for fallback-path biomarkers)
- Added `test_cbm_conditions_have_display_names` and `test_taxonomy_cbm_intersection_always_has_display_name` — guards `_build_relevance` invariant
- Added comment on `next(iter(citations.values()), "")` documenting the single-citation fallback assumption
- Data-integrity test initially discovered real inconsistency: 15 taxonomy condition codes (NAFLD, anemia, hyperthyroidism, etc.) are absent from cbm — intentional capstone scope gap, documented with a comment in `_build_relevance`

**PR:** #25
