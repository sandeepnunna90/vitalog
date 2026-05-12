# Task 11 — Trend Engine

## Context

Per architecture §5.4.1, the Trend Engine is deterministic (no LLM). It takes a patient + canonical biomarker, pulls all records from persistence, joins to the taxonomy for canonical units + condition-aware target ranges, and returns a structured `TrendSeries`. This powers the trend chart and feeds the Summary Generator.

## Dependencies

- Task 01 (schemas — `TrendPoint`, `TrendSeries`, `TargetBand`)
- Task 08 (persistence — `BiomarkerRepository`)
- Task 09 (taxonomy — guideline ranges, condition mappings)

## In scope

`src/intelligence/trend_engine.py`:

- `TrendEngine.get_trend(patient_id, canonical_id) -> TrendSeries`:
  - Pull all `BiomarkerRecord` for patient/canonical.
  - Sort by `collection_date`.
  - Load `TaxonomyEntry` for canonical units + guideline ranges.
  - Determine condition-aware target band: read patient profile, find matching condition, pick the appropriate guideline range (e.g., for Mark with diabetes, HbA1c target is ADA <7.0%; for a non-diabetic patient, the generic range would apply).
  - If no condition match, fall back to generic published range and label as such.
  - Output: `TrendSeries(points: List[TrendPoint], target_band: TargetBand, units, source_citation)`.
- `src/intelligence/patient_profile.py`:
  - Loads `reference_data/mark_profile.json` (hardcoded for capstone — real onboarding is if-time task 18).
  - Profile shape: conditions[], medications[], allergies[].
- `TrendEngine` is pure Python — no LLM, no Gateway calls. Fully unit-testable.

## Out of scope (deferred)

- Multi-biomarker trend grouping (Scenario 4 / NLQ — if-time task 17).
- Predictive trends — never (architecture §12: no predictions).
- Per-record annotations on trend points — v1.

## Files to create

- `src/intelligence/__init__.py`
- `src/intelligence/trend_engine.py`
- `src/intelligence/patient_profile.py`
- `reference_data/mark_profile.json`
- `tests/intelligence/test_trend_engine.py`
- `tests/intelligence/test_patient_profile.py`

## Architecture references

- `docs/Vitalog_architecture.md` §5.4.1 — Trend Engine
- `docs/Vitalog_architecture.md` §12 OQ1 — condition-specific range overlay (documented as open question; capstone picks the simplest path)
- `docs/Vitalog_PRD_v2.md` §Functional Requirements "Trend View → Longitudinal chart"
- `docs/vitalog_roadmap.md` §4 Intelligence

## Step-by-step

1. Write `reference_data/mark_profile.json`: T2D, HTN, borderline thyroid; current meds (metformin, lisinopril, etc.); no allergies of note.
2. Implement `PatientProfile.load(patient_id)` — just JSON load for capstone.
3. Implement `TrendEngine.get_trend`:
   - Repo call → records.
   - Taxonomy join.
   - Condition matching for target band.
   - Construct `TrendSeries`.
4. Unit tests with mocked repository: empty, single point, full 9-point hero trend.

## Acceptance criteria

- [ ] `TrendEngine.get_trend("mark", "vitalog:hba1c")` returns 9 sorted points spanning 2022–2026.
- [ ] Target band reflects ADA diabetes target (<7.0%), not the generic 4–5.6% range.
- [ ] `source_citation` populated with the guideline source string from taxonomy.
- [ ] Empty-record case returns `TrendSeries(points=[], ...)` cleanly.
- [ ] `mypy src/intelligence --strict` clean.

## Verification

- `pytest tests/intelligence -q`
- `python -c "from src.intelligence.trend_engine import TrendEngine; t = TrendEngine().get_trend('mark', 'vitalog:hba1c'); print(t)"`
- Output shows 9 points sorted ascending with HbA1c trend.
