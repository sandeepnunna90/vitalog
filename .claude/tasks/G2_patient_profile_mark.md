# G2 — Patient profile (Mark hardcoded)

**Epic:** Top Layer
**Points:** 3
**Priority:** High
**Depends on:** A3
**Architecture refs:** §6.1; PRD v2 Patient Profile row; project CLAUDE.md Gotchas

## User story

As the founder running the capstone demo,
I want Mark's patient profile (T2D, HTN, hypothyroid + meds + allergies) hardcoded in `reference_data/mark_profile.json` and loaded at startup,
So that the demo flow has a stable, well-understood patient context without needing a user-management system.

## Why this matters

Project CLAUDE.md Gotchas: "Mark's patient profile is hardcoded in `reference_data/mark_profile.json` for the capstone. Do not load it from Supabase unless task 18 (if-time) has landed." Keeping this story clean and minimal means F1/F5 have a stable profile to operate on without a half-built user system.

## Acceptance criteria

1. **Given** the file `reference_data/mark_profile.json`, **When** I open it, **Then** it contains: a stable UUID `mark_capstone`, full name "Mark Capstone" (synthetic), DOB, conditions `["T2D", "HTN", "Hypothyroid"]`, medications (metformin, lisinopril, levothyroxine, recent statin) each with `name + start_date + dose`, allergies (e.g., penicillin).
2. **Given** the loader, **When** any service calls `load_patient_profile()`, **Then** it returns the validated Pydantic `PatientProfile` model — no Supabase read.
3. **Given** the audit-log integration, **When** the profile is loaded at server startup, **Then** an audit-log event of type `profile_loaded` is recorded with profile_version_hash.
4. **Given** the contract, **When** F5 generates a cardiology summary, **Then** the conditions and medications sections are pulled from this loaded profile.
5. **Given** capstone scope, **When** I `grep "mark_profile" src/`, **Then** the only loader is in `src/reference_data/patient_profile.py`; no service constructs a profile from Supabase.
6. **Given** the recent-statin entry, **When** F5 detects data gaps, **Then** the statin's `start_date` is used to flag the "no post-statin lipid panel" gap.

## Files to create / modify

- `reference_data/mark_profile.json`
- `src/reference_data/patient_profile.py` — `load_patient_profile()`, returns `PatientProfile`
- `src/reference_data/patient_profile_schemas.py` — `PatientProfile`, `Medication`, `Allergy` Pydantic models
- `tests/reference_data/test_patient_profile.py`

## Implementation notes

- Synthetic personal details (name, DOB, address fields): use clearly-fake values per A2 convention (`"Mark Capstone"`, DOB `1969-04-15`, etc.). Document explicitly that this is a demo profile.
- The statin start_date is the demo's "data gap" anchor. Pick a date approximately 2–3 months before the demo so "no post-statin lipid panel" is a believable gap.
- Conditions encoded as canonical condition codes that match the condition→biomarker map keys (e.g., `"T2D"` matches `biomarker_groups.json` key).
- The loader caches in process memory after first load. Hot-reload is not needed at capstone scale.
- The `PatientProfile` model is the contract for F1 (condition-aware range overlay), F3 (NLQ condition references), F5 (summary), and G1 (MCP tools that need patient_id).

## Verification

- `pytest tests/reference_data/test_patient_profile.py -q`
- Manual: load the profile in a Python REPL, confirm structure
- Integration: F5 generates a summary that reflects Mark's conditions and meds correctly

## INVEST check

- [x] Independent — only A3 required
- [x] Negotiable — exact medication list flexible
- [x] Valuable — gates F5 and the demo
- [x] Estimable — well-bounded
- [x] Small — 3 pts
- [x] Testable — load + validate

## Deferred (explicitly out of this story)

- User-entered profile via MCP onboarding flow — v1 (architecture §11 capstone scope note: "Not extracted from documents in v1")
- Multi-patient support — v1
- Loading profile from Supabase — v1 ("task 18" per project CLAUDE.md Gotchas)

## Notes / changelog

### Implementation (2026-05-17)

**Files created:**
- `reference_data/mark_profile.json` — hardcoded profile with conditions `["T2D", "HTN", "hypothyroidism"]`, medications (metformin, lisinopril, levothyroxine, rosuvastatin started 2026-02-15), allergy (penicillin), and `note` field labelling it synthetic demo data
- `src/reference_data/patient_profile_schemas.py` — `Medication`, `Allergy`, `PatientProfile` Pydantic v2 models with `ConfigDict(strict=True)`
- `src/reference_data/patient_profile.py` — `load_patient_profile()` with `@lru_cache(maxsize=1)`; injects `profile_version_hash` (SHA-256 of raw JSON bytes)
- `tests/reference_data/test_patient_profile.py` — 8 unit tests covering all ACs

**Files modified:**
- `src/reference_data/__init__.py` — re-exports `load_patient_profile`, `MARK_PATIENT_ID`, `PatientProfile` for consistent public API surface

**Key design decisions:**
- `model_validate(..., strict=False)` used at load time to allow JSON string→UUID/date coercion; model stays `strict=True` for all other construction paths
- Condition codes use `biomarker_groups.json` keys exactly (`T2D`, `HTN`, `hypothyroidism`)
- Rosuvastatin `start_date: 2026-02-15` is the F5 data-gap anchor for "no post-statin lipid panel"
- AC3 (audit-log `profile_loaded` event) deferred to G1 (MCP server startup); G2 exposes `profile_version_hash` to support it

**PR review fixes:**
- Changed CWD-relative path in test to `Path(__file__).parent.parent.parent / "src/reference_data/patient_profile.py"` 
- Added `note: str` to `PatientProfile` schema so the JSON demo-label field is validated rather than silently dropped
- Re-exported `MARK_PATIENT_ID`, `load_patient_profile`, `PatientProfile` from `src/reference_data/__init__.py`

**PR:** #24

### Refactor (2026-05-19) — remove medications and allergies

**Context:** Lab reports don't contain medication or allergy data. The original G2 implementation included these fields without a real data source, making the profile misleading. This refactor removes them end-to-end.

**Files modified:**
- `reference_data/mark_profile.json` — removed `medications`/`allergies` arrays; bumped `profile_version` to `1.1.0`
- `src/reference_data/patient_profile_schemas.py` — removed `Medication`, `Allergy` classes and their fields from `PatientProfile`
- `src/persistence/models.py` — removed `medications`/`allergies` from `PatientProfileRow` and `PatientProfileCreate`
- `src/intelligence/summary_schemas.py` — removed `medications_section` from both `SummaryOutput` (LLM schema) and `Summary`
- `src/intelligence/summary_generator.py` — bumped `_PROMPT_VERSION` to `"v3"`; `_build_inputs` now produces conditions-only `profile_text`
- `src/intelligence/annotator.py` — removed `"medications_section"` from `_VALID_SECTIONS` frozenset
- `src/intelligence/exporters/pdf_exporter.py` — removed `"medications_section"` from `_SECTION_LABELS`
- `src/intelligence/exporters/markdown_exporter.py` — removed `"medications_section"` from `_SECTION_LABELS`
- `src/mcp_server/tools/prepare_summary.py` — removed `medications_section` block from formatted output
- `src/orchestration/workflows.py` — removed `medications_section` from `GenerateSummaryResult`
- `prompts/summary/v3.md` — new file; OUTPUT SECTIONS reduced from 6 to 5 (no `medications_section`)
- `tests/intelligence/test_summary_generator.py` — updated `_good_output()`, mocks, prompt version
- `tests/intelligence/test_exporters.py` — removed `medications_section` from `_CONTENT_JSON`; added `## Current Medications` absence assertion
- `tests/intelligence/test_annotator.py` — removed `medications_section` from fixtures
- `tests/mcp_server/test_tools_smoke.py` — removed `medications_section` from mock objects
- `tests/reference_data/test_patient_profile.py` — removed statin/allergy tests; added `test_profile_version_is_1_1_0` and `test_profile_has_no_medications_or_allergies`

**Key design decisions:**
- `conditions` retained (they contextualize lab results for guideline range overlays); only medication/allergy data removed
- No DB migration needed — `PatientProfileRow`/`PatientProfileCreate` are Pydantic models only; no `patient_profile_repository.py` exists
- `json_exporter.py` unaffected — passes `content_json` dict through without enumerating keys

**PR:** #33
