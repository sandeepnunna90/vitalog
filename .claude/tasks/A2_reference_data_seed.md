# A2 — Reference data seed

**Epic:** Foundation
**Points:** 5
**Priority:** Critical
**Depends on:** A1
**Architecture refs:** §6.3, §5.2, ADR-03; PRD v2 Data Requirements

## User story

As the founder building Vitalog,
I want a versioned, in-repo set of reference data files (taxonomy, LOINC subset, UCUM, conditions, specialists, guidelines),
So that Normalization, Trend Engine, and Summary Generator have a single source of truth for biomarker identity, units, and target ranges before any other concern is built.

## Why this matters

Normalization must be deterministic, and the Summary Generator must cite published guideline sources. Both depend on reference data being loaded from disk, version-controlled, and code-reviewable. Building these JSON files first unblocks E1/E3/F1/F4/F5 and gives the eval corpus ground truth to align against.

## Acceptance criteria

1. **Given** the repo is freshly cloned, **When** I run `python -c "from src.reference_data import load_all; load_all()"`, **Then** all six reference files load without error and the count of taxonomy entries is exactly 30.
2. **Given** the biomarker taxonomy seed, **When** I look up `"HbA1c"` via the alias index, **Then** it resolves to `vitalog_id = "hba1c"` with LOINC code `"4548-4"`, canonical unit `"%"`, and at least one alias each for capital, lowercase, and "Hemoglobin A1c" spellings.
3. **Given** the guideline ranges file, **When** I look up HbA1c, **Then** I get `ADA_target: "<7.0%"`, `ADA_normal: "<5.7%"`, and a citation string pointing to the ADA Standards of Care publication.
4. **Given** the UCUM units file, **When** I request conversion from `"mmol/mol"` to `"%"` for HbA1c, **Then** the conversion rule yields a result within 0.05% of the IFCC formula.
5. **Given** the condition→biomarker map, **When** I look up `"T2D"`, **Then** I get at minimum `hba1c`, `fasting_glucose`, `egfr`, and the lipid panel markers.
6. **Given** the specialist content templates, **When** I look up `("cardiology", "first_visit")`, **Then** I get a section list that drives F5's summary generator.

## Files to create / modify

- `reference_data/biomarker_taxonomy.json` — 30 entries (per architecture §5.2)
- `reference_data/loinc_subset.json` — codes referenced by the taxonomy
- `reference_data/ucum_units.json` — units + conversion rules
- `reference_data/condition_biomarker_map.json`
- `reference_data/specialist_content_templates.json`
- `reference_data/guideline_ranges.json` — ADA / ACC / AHA / ATA with citations
- `src/reference_data/__init__.py` — `load_all()`, `load_taxonomy()`, `lookup_alias()`, `lookup_guideline()`
- `tests/reference_data/test_loading.py`
- `tests/reference_data/test_taxonomy_invariants.py`

## Implementation notes

- The 30 taxonomy entries must cover everything Mark's HbA1c + cardiology demo touches. Suggested coverage: HbA1c, fasting glucose, postprandial glucose, lipid panel (total cholesterol, LDL-C, HDL-C, triglycerides, non-HDL-C), eGFR, creatinine, urine ACR, BP (systolic, diastolic), TSH, free T4, ALT, AST, hsCRP, vitamin D (25-OH), vitamin B12, ferritin, CBC core (Hgb, Hct, WBC, platelets), basic metabolic panel core (sodium, potassium, chloride, BUN, glucose), fructosamine. Pick exactly 30.
- Every taxonomy entry carries: `vitalog_id`, `canonical_name`, `loinc_code`, `ucum_unit`, `unit_conversions`, `aliases`, `conditions`, `guideline_ranges`, `guideline_citations`, `verification_tier: "canonical"`, `verified: true`.
- Guideline ranges are NOT LLM-generated — they're transcribed from the cited source. Keep a `provenance` block per entry.
- File format: stable key ordering for clean diffs; trailing newline.
- `load_all()` is the only public entry point services should use; tests assert that no service imports the JSON paths directly.

## Verification

- `pytest tests/reference_data/ -q` — all unit tests green
- `python -m src.reference_data.lint` — invariant linter (every taxonomy entry has all required fields, every guideline citation has a URL, every LOINC code referenced by the taxonomy is in the LOINC subset)
- Manual: spot-check three entries against their cited guideline document

## INVEST check

- [x] Independent — only A1 is required
- [x] Negotiable — exact 30 choices flexible; coverage of demo flow fixed
- [x] Valuable — unblocks E1, E3, F1, F4, F5
- [x] Estimable — well-bounded data curation work
- [x] Small — 5 pts (data + thin loader + tests)
- [x] Testable — every AC verifiable

## Deferred (explicitly out of this story)

- Loading taxonomy from Supabase (capstone uses in-repo JSON per ADR-03)
- Tier 2 fuzzy match and Tier 3 LOINC lookup (v1 — see E2 for the pending queue stub)
- Auto-promote logic for new taxonomy entries (v2)

## Notes / changelog

_(append after work is done)_
