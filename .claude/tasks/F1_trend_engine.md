# F1 — Trend Engine (deterministic, no LLM)

**Epic:** Intelligence
**Points:** 3
**Priority:** Critical
**Depends on:** A3, E1
**Architecture refs:** §5.4.1; PRD v2 Trend View row; demo hero flow

## User story

As Mark walking into my cardiology appointment,
I want to see all my HbA1c results across every lab on one chart, with the ADA target range shaded behind them,
So that — for the first time — I can see my 4-year trend at a glance and bring it to my doctor.

## Why this matters

This is the headline demo moment. P4 (determinism where possible) and the architecture mandate "Pure code, no LLM" mean the chart is exact, fast, and never hallucinates. The trend engine is what turns a pile of records into a story.

## Acceptance criteria

1. **Given** Mark has 9 HbA1c records spanning 3 labs over 4 years, **When** I call `TrendEngine.get_trend(patient_id, canonical_id="hba1c")`, **Then** I receive a chart-ready structure with: 9 sorted points (date, canonical_value, lab_source, record_id), the ADA target band `<7.0%`, and the ADA normal band `<5.7%`.
2. **Given** Mark's patient profile lists T2D as a condition, **When** the trend runs, **Then** the displayed target band uses the T2D-specific ADA target (`<7.0%`), NOT the generic non-diabetic normal range.
3. **Given** a patient with no condition match, **When** the trend runs, **Then** the displayed band falls back to the published guideline normal range.
4. **Given** the trend, **When** I inspect a point, **Then** every point carries its `record_id`, `lab_source`, `verified_by`, and `extraction_confidence` — so the trend is auditable per-point.
5. **Given** review-band records (`verified_by="pending_user"`), **When** the trend runs, **Then** those records are EXCLUDED from the trend until confirmed (they're visible in the review queue, not in trends).
6. **Given** the contract, **When** I `grep "anthropic\|Gateway" src/intelligence/trend_engine.py`, **Then** I find ZERO matches (pure deterministic code).

## Files to create / modify

- `src/intelligence/__init__.py`
- `src/intelligence/trend_engine.py`
- `src/intelligence/trend_schemas.py` — `TrendPoint`, `TrendBand`, `TrendResult`
- `src/intelligence/range_overlay.py` — selects condition-specific target band from guideline data
- `tests/intelligence/test_trend_engine.py`
- `tests/intelligence/test_range_overlay.py`

## Implementation notes

- The engine fetches via `BiomarkerRepository.list_for_patient(patient_id, canonical_id)`, filtered to `verified_by IN ("auto", "user", "admin")`. The `pending_user` rows are excluded — but the engine returns `pending_review_count` so the UI/MCP tool can prompt the user.
- Range overlay logic: look at the patient's conditions, find the most-specific guideline range from the taxonomy entry's `guideline_ranges` (e.g., `ADA_target_T2D` beats `ADA_normal`). If no condition match, fall back to `ADA_normal` (or equivalent for non-diabetes biomarkers).
- The output is chart-ready: points sorted by date ascending, bands as `(label, lower, upper, citation)` tuples. The MCP tool consumes this structure; capstone doesn't render to image — Claude Desktop describes/renders it.
- Provenance per point is preserved so the consumer (NLQ, Summary Generator) can cite individual points.
- Performance: trends are typically <100 points. No caching layer needed at capstone scale.

## Verification

- `pytest tests/intelligence/test_trend_engine.py -q` — covers happy path, no records, only pending_user records, conditioned vs unconditioned range overlay
- `pytest tests/intelligence/test_range_overlay.py -q`
- After H1 lands: invoke `TrendEngine.get_trend(mark_id, "hba1c")` against the hero dataset, confirm 9 points + ADA T2D band
- Demo verification: this is one of the demo moments — works end-to-end via MCP

## INVEST check

- [x] Independent — A3 + E1 required
- [x] Negotiable — exact band-selection rule flexible
- [x] Valuable — the headline demo moment
- [x] Estimable — well-bounded deterministic code
- [x] Small — 3 pts
- [x] Testable — easy to fixture

## Deferred (explicitly out of this story)

- Smoothing / trend-line fitting — v1
- Anomaly detection on trends — v2
- Cross-biomarker correlation views — v2
- Image rendering (PNG/SVG) of charts — v1 web UI

## Notes / changelog

### Implementation (2026-05-17)

**Files created:**
- `src/intelligence/trend_schemas.py` — `TrendPoint`, `TrendBand`, `TrendResult` Pydantic v2 strict models
- `src/intelligence/range_overlay.py` — `select_bands()`, `_parse_range()`, `_match_authority()`; condition → band selection via `_CONDITION_PREFERRED_SUFFIXES`
- `src/intelligence/trend_engine.py` — `TrendEngine.get_trend(patient_id, canonical_id, patient_conditions=None)`; pure deterministic; `patient_conditions` param decouples from G2
- `tests/intelligence/test_trend_engine.py` — 10 unit tests; repo mocked
- `tests/intelligence/test_range_overlay.py` — 9 unit tests (8 original + 1 from PR review fix); uses real `lookup_guideline("hba1c")`

**Files modified:**
- `src/intelligence/__init__.py` — exports `TrendEngine`, `TrendBand`, `TrendPoint`, `TrendResult`

**Key design decisions:**
- `patient_conditions` param (not loading `mark_profile.json`) — G2 hasn't landed; decouples F1 from profile store
- `find_by_canonical_id()` used as-is (no new repo method) — already exists, in-memory `pending_user` filter appropriate for <100 points
- Both `_normal` band AND condition-specific `_target_*` band returned (AC1 explicitly names both for T2D)
- `_match_authority()` finds longest matching citation key prefix — handles compound authorities like `ACC_AHA` where `key.split("_")[0]` would return `"ACC"` (bug caught in PR review)
- `TrendBand.raw_range` preserves original taxonomy string for downstream consumers

**PR review fixes (PR #19):**
- Fixed `_make_band` authority extraction: `key.split("_")[0]` → `_match_authority()` helper; `band.citation` was always `None` for ACC_AHA biomarkers (LDL, HDL, total cholesterol, triglycerides)
- Fixed `test_no_anthropic_import` hardcoded `cwd`: replaced `/Users/sandeepnunna/...` with `Path(__file__).parent.parent.parent`; this caused the CI test to raise `FileNotFoundError` on GitHub Actions
- Added `test_acc_aha_compound_authority_citation_not_none` to cover the citation fix
