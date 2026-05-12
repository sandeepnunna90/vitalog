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
- Conditions encoded as canonical condition codes that match the condition→biomarker map keys (e.g., `"T2D"` matches `condition_biomarker_map.json` key).
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

_(append after work is done)_
