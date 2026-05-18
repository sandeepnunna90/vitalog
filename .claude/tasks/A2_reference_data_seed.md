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
- `reference_data/biomarker_groups.json` — replaced condition_biomarker_map.json in F5; specialist_content_templates.json deleted in F5
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

### What each file does — plain terms (2026-05-13)

- **`biomarker_taxonomy.json`** — The master dictionary. For each of the 30 biomarkers (HbA1c, LDL, eGFR, etc.) it stores: what to call it, all its nicknames, its LOINC code, what unit it uses, and its normal/abnormal ranges. Everything else links back to this.
- **`loinc_subset.json`** — LOINC is a global standard code system for lab tests (like ICD-10, but for lab results). This file stores metadata for the 30 specific LOINC codes used by the taxonomy — the "official ID card" for each test.
- **`ucum_units.json`** — A unit conversion table. Labs report the same biomarker in different units (e.g., blood glucose as mg/dL in the US or mmol/L in Europe). This file stores the math to convert between them.
- **`biomarker_groups.json`** (replaces `condition_biomarker_map.json`, F5) — Answers "which biomarkers are grouped with which condition?" Flat `biomarkers` list per condition with embedded guideline citations. `specialist_content_templates.json` was deleted in F5 — encoded clinical assumptions with no defensible authority.
- **`guideline_ranges.json`** — The published "what's normal/abnormal" thresholds from medical organizations (ADA, ACC/AHA, etc.) with full citations and DOI links. The Summary Generator cites these directly when it says "your LDL is above the ACC/AHA target."

One-line distinction: **taxonomy = identity**, **LOINC = official IDs**, **UCUM = unit math**, **biomarker groups = condition-grouping reference**, **guideline ranges = thresholds with sources**.

### Data provenance (2026-05-13)

All reference data was **structured by Claude (AI)** but the actual numbers, codes, and citations are drawn from real, published sources — not generated by the model. Details:

**Guideline thresholds — transcribed from published papers:**
- ADA Standards of Care 2024 — https://doi.org/10.2337/dc24-S001
- 2018 ACC/AHA Cholesterol Guideline — https://doi.org/10.1016/j.jacc.2018.11.003
- 2017 ACC/AHA Hypertension Guideline — https://doi.org/10.1016/j.jacc.2017.11.006
- ATA Hypothyroidism Guidelines 2014 — https://doi.org/10.1089/thy.2014.0028
- KDIGO 2024 CKD Guideline — https://doi.org/10.1016/j.kint.2023.10.018
- Endocrine Society Vitamin D 2011 — https://doi.org/10.1210/jc.2011-0385

**LOINC codes — from Regenstrief Institute (loinc.org):** real, registered codes (e.g., `4548-4` for HbA1c).

**UCUM conversion factors — from ucum.org:** derived from molecular weights (physical constants), not estimated.

**What AI contributed:** JSON structure, alias lists, biomarker selection, and organizing which entries belong together. The numbers themselves were not generated by the model.

**Recommendation:** spot-check key thresholds (HbA1c target, LDL risk targets, BP targets) against the cited papers before any clinical use. All DOIs in the JSON files are live links to the actual publications.
