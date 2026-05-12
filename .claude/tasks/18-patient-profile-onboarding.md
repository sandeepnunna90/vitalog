# Task 18 — Patient profile onboarding *(if-time)*

## Context

**If-time only.** Capstone ships with `reference_data/mark_profile.json` hardcoded (task 11). If time allows in Week 2 or early Week 3, replace the hardcoded profile with a minimal onboarding flow exposed as an MCP tool. PRD v2 §Functional Requirements lists this as a real requirement, but Mark's profile being JSON is acceptable for demo.

## Dependencies

- Task 01 (schemas — `PatientProfile`)
- Task 08 (persistence — patient table + repository)
- Task 14 (MCP server — new tool added)

## In scope

`src/persistence/repositories/patient_repository.py`:

- `PatientRepository.upsert_profile(patient_id, profile)`.
- `PatientRepository.get_profile(patient_id)`.

`src/mcp_server/tools/upsert_patient_profile.py`:

- Input: `PatientProfile` (conditions, medications with start dates, allergies).
- Output: confirmation + warning if any condition has no taxonomy mapping (for future v2 onboarding-driven retrieval).

Migration: `migrations/006_patient_profiles.sql`.

Update `src/intelligence/patient_profile.py` (task 11) to read from the repository instead of JSON. JSON file kept as a seed loader for fresh setups.

## Out of scope (deferred)

- Onboarding wizard UX (v1 web UI).
- Med interaction checks (never — out of scope for product).
- Condition graphing (v1).

## Files to create

- `src/persistence/repositories/patient_repository.py`
- `src/mcp_server/tools/upsert_patient_profile.py`
- `migrations/006_patient_profiles.sql`
- Update `src/intelligence/patient_profile.py`
- `tests/persistence/test_patient_repository.py`
- `tests/mcp_server/test_upsert_patient_profile.py`

## Architecture references

- `docs/Vitalog_architecture.md` §5.4 — patient profile usage in summaries
- `docs/Vitalog_PRD_v2.md` §Functional Requirements "Patient Profile → Onboarding"

## Step-by-step

1. Write migration for `patient_profiles` table.
2. Implement `PatientRepository`.
3. Implement MCP tool.
4. Update `patient_profile.py` to prefer repo; fall back to JSON.
5. Tests.
6. Update MCP server registration to include the new tool.

## Acceptance criteria

- [ ] `upsert_patient_profile` MCP tool works from Claude Desktop.
- [ ] Mark's profile written via this tool produces identical Summary output to the hardcoded JSON version.
- [ ] Repository round-trips profile.

## Verification

- `pytest tests/persistence/test_patient_repository.py tests/mcp_server/test_upsert_patient_profile.py -q`
- Via Claude Desktop: upsert Mark; run prepare_summary; output matches pre-onboarding version.
