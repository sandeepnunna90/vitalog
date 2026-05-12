# Task 09 — Normalization: Tier 1 + UCUM + duplicate detection + pending queue

## Context

Per architecture §5.2, normalization resolves raw biomarker candidates to canonical taxonomy entries (LOINC + UCUM aligned), converts units to canonical form, detects duplicates, and stages unmatched candidates for admin review. Capstone scope: Tier 1 (exact alias match) + Tier 4 (pending queue) only; Tiers 2/3 deferred to v1.

## Dependencies

- Task 01 (schemas — `BiomarkerRecord`, `TaxonomyEntry`)
- Task 03 (eval corpus — taxonomy aliases tested against extracted names)
- Task 07 (structurer — produces the `BiomarkerCandidate[]` this consumes)
- Task 08 (persistence — `TaxonomyRepository`, `BiomarkerRepository`, and the pending-taxonomy table)

## In scope

`src/normalization/`:

- `taxonomy.py`:
  - Loads `reference_data/biomarker_taxonomy.json` — ~30 seed entries: HbA1c, fasting glucose, total cholesterol, HDL, LDL, triglycerides, ALT, AST, creatinine, BUN, eGFR, TSH, free T4, sodium, potassium, calcium, hemoglobin, hematocrit, platelets, WBC, RBC, lipoprotein(a), CRP, fibrinogen, microalbumin, urinalysis essentials. Each: `vitalog_id`, canonical_name, LOINC code, UCUM unit, aliases (5–15 common variants), condition_mappings (`diabetes`, `hypertension`, `thyroid`, etc.), guideline_ranges with source citation (ADA/ACC/AHA/ATA).
  - In-memory index by canonical_id, by alias (case-insensitive, whitespace-normalized).
- `tier1.py` — `Tier1Resolver.resolve(candidate) -> TaxonomyEntry | None`. Pure dict lookup against the alias index.
- `unit_conversion.py`:
  - `UCUM_CONVERSIONS` table for the units encountered in eval corpus: `mg/dL ↔ mmol/L` for glucose, cholesterol; `%` for HbA1c (no conversion needed); `pg/mL` and `ng/dL` for thyroid hormones; `mEq/L ↔ mmol/L` for electrolytes.
  - `convert(value, from_unit, to_unit, canonical_unit) -> Decimal`.
- `duplicate_detection.py` — `is_duplicate(record, existing_records)` checks `(canonical_id, collection_date, value within 0.5% tolerance)`. Returns both records flagged; neither auto-deleted.
- `pending_queue.py` — `enqueue(candidate, similarity_scores)` writes to `pending_taxonomy` table for admin review. Capstone: founder resolves manually.
- `normalizer.py` — orchestration: `Normalizer.normalize(candidates) -> NormalizationResult(records, pending, duplicates)`.

## Out of scope (deferred)

- Tier 2 fuzzy matching (string similarity + embeddings) — v1.
- Tier 3 live LOINC lookup — v1.
- Confidence-based routing for taxonomy review — v1.
- User-facing taxonomy review prompts — v1.
- Auto-promote logic — v2.

## Files to create

- `src/normalization/__init__.py`
- `src/normalization/taxonomy.py`
- `src/normalization/tier1.py`
- `src/normalization/unit_conversion.py`
- `src/normalization/duplicate_detection.py`
- `src/normalization/pending_queue.py`
- `src/normalization/normalizer.py`
- `reference_data/biomarker_taxonomy.json` (30 seed entries)
- `reference_data/ucum_conversions.json`
- `scripts/resolve_pending_taxonomy.py` (founder CLI for clearing the queue)
- `tests/normalization/test_*.py`

## Architecture references

- `docs/Vitalog_architecture.md` §5.2 — Normalization Service
- `docs/Vitalog_architecture.md` §6.3 — Reference data layout
- `docs/Vitalog_architecture.md` ADR-03 — taxonomy strategy
- `docs/Vitalog_PRD_v2.md` §Functional Requirements "Normalization" rows
- `docs/vitalog_roadmap.md` §4 Normalization

## Step-by-step

1. Author `reference_data/biomarker_taxonomy.json` with the 30 seed entries (research-light: pull LOINC codes from official site, UCUM units from common usage, aliases from your eval corpus extracted names + a few standard variations).
2. Implement `taxonomy.py` loader + alias index.
3. Implement `tier1.py`, `unit_conversion.py`, `duplicate_detection.py` in isolation with unit tests.
4. Implement `pending_queue.py` writing to `pending_taxonomy` table via the repository from task 08.
5. Implement `Normalizer.normalize` orchestration.
6. Write `scripts/resolve_pending_taxonomy.py` — list, view, resolve (link to canonical or mark `not_a_biomarker`).
7. Integration test: run normalizer over hero data ingestion output; assert all 30+ records resolve via Tier 1, zero land in pending.

## Acceptance criteria

- [ ] Taxonomy seed has ≥30 entries with valid LOINC codes.
- [ ] Aliases cover every biomarker name encountered in eval corpus.
- [ ] Unit conversions accurate to 4 decimal places for mg/dL ↔ mmol/L (glucose: 1 mmol/L = 18.0182 mg/dL).
- [ ] Duplicate detection: same canonical_id + date + value within 0.5% → flagged, both stored.
- [ ] Pending queue script can list and resolve entries.
- [ ] `mypy src/normalization --strict` clean.

## Verification

- `pytest tests/normalization -q`
- `python -m src.normalization.normalizer` against pipeline output → 0 pending on hero data
- `python scripts/resolve_pending_taxonomy.py list` runs (empty list expected on hero data)
