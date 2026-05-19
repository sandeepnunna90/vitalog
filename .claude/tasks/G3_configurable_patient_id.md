# G3 — Configurable patient ID via env var

**Epic:** Top Layer
**Points:** 1
**Depends on:** G2
**Status:** ✅

## User story

As a developer testing the app with real documents,
I want to set `VITALOG_PATIENT_ID` in my `.env` to use my own UUID,
So that I can upload and query my own lab reports without being locked to Mark's hardcoded ID.

## Acceptance criteria

1. When `VITALOG_PATIENT_ID` is set to a valid UUID, the MCP guard accepts that UUID and rejects all others.
2. When `VITALOG_PATIENT_ID` is unset, the guard falls back to `MARK_PATIENT_ID` — no behaviour change.
3. When `VITALOG_PATIENT_ID` is set to an invalid (non-UUID) value, the server raises `ValueError` at startup with a clear message.
4. `.env.example` documents the new var.

## Setup required (one-time, per user)

1. Generate a UUID: `python3 -c "import uuid; print(uuid.uuid4())"`
2. Insert a patient row in Supabase: `INSERT INTO patient (patient_id, name, dob) VALUES ('<uuid>', 'Your Name', '1990-01-01');`
3. Add `VITALOG_PATIENT_ID=<uuid>` to `.env`

## Files changed

- `src/mcp_server/tools/_guard.py` — reads `VITALOG_PATIENT_ID` at import; falls back to `MARK_PATIENT_ID`
- `.env.example` — documents the new optional var
- `tests/mcp_server/test_tools_smoke.py` — new test for env-var path via `monkeypatch`

## Implementation (2026-05-19)

`_ACCEPTED_PATIENT_ID` is a module-level singleton evaluated at startup via `_load_accepted_patient_id()`. All six MCP tools call `validate_patient_id()` which checks against this singleton — no change to the public API.

**PR:** #35
