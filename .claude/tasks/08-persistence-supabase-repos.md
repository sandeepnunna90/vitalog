# Task 08 — Persistence: Supabase + repositories

## Context

Per architecture §6 and ADR-04, persistence is Supabase Postgres + Storage, accessed through a Repository pattern that hides the Supabase client behind interfaces. Storage policy is **classification-gated** per §7.6: `lab_report` and `recognized_unsupported` retained; `not_supported` discarded with audit row only.

## Dependencies

- Task 01 (schemas)
- Task 04 (classifier — feeds `DocumentCategory` into storage decision)
- Task 07 (pipeline — produces records to persist)

## In scope

`src/persistence/` module:

- `client.py` — Supabase client init from env vars; one shared instance.
- `repositories/biomarker_repository.py` — `add(record)`, `list_by_patient(patient_id)`, `list_by_canonical(patient_id, canonical_id)`, `get(record_id)`.
- `repositories/document_repository.py` — `add(document)`, `get(document_id)`, `list_by_patient(patient_id)`.
- `repositories/audit_log_repository.py` — append-only `log(event: AuditEvent)`.
- `repositories/taxonomy_repository.py` — read taxonomy + pending-taxonomy queue (task 09 adds the writer).
- `storage.py` — `Storage.store_raw(document_id, bytes, category)`:
  - `lab_report` → Supabase Storage bucket `raw_documents`.
  - `recognized_unsupported` → same bucket, separate folder.
  - `not_supported` → no-op; returns `None`; audit event logged separately.
- `migrations/` SQL files:
  - `001_documents.sql` (id, patient_id, category, subtype, classification_confidence, storage_path nullable, created_at)
  - `002_biomarker_records.sql` (everything from `BiomarkerRecord` schema)
  - `003_audit_log.sql` (event_type, actor, patient_id nullable, document_id nullable, payload jsonb, ts)
  - `004_taxonomy.sql` (taxonomy seed table) + `005_pending_taxonomy.sql` (queue table)
- `tests/persistence/` — use a `FakeSupabase` in-memory implementation for unit tests; one integration test gated by `VITALOG_LIVE_SUPABASE=1`.

## Out of scope (deferred)

- Row-Level Security policies (v1.5 — capstone uses synthetic data, no PHI).
- Application-level encryption (v1.5).
- Soft delete + user-initiated purge (v1).
- Multi-tenant patient_id resolution (capstone has a single patient: Mark).

## Files to create

- `src/persistence/__init__.py`
- `src/persistence/client.py`
- `src/persistence/storage.py`
- `src/persistence/repositories/__init__.py`
- `src/persistence/repositories/biomarker_repository.py`
- `src/persistence/repositories/document_repository.py`
- `src/persistence/repositories/audit_log_repository.py`
- `src/persistence/repositories/taxonomy_repository.py`
- `migrations/001_documents.sql` through `005_pending_taxonomy.sql`
- `tests/persistence/fakes.py` (FakeSupabase + in-memory storage)
- `tests/persistence/test_*.py`

## Architecture references

- `docs/Vitalog_architecture.md` §6 — Data architecture
- `docs/Vitalog_architecture.md` §7.6 — Classification-gated storage policy
- `docs/Vitalog_architecture.md` ADR-04 — Supabase + migration triggers
- `docs/Vitalog_PRD_v2.md` §Data Requirements
- `docs/Vitalog_PRD_v2.md` §Compliance — classification-gated retention

## Step-by-step

1. Pre-provision Supabase project (free tier); save URL + service key into `.env`.
2. Write migrations; apply via Supabase SQL editor.
3. Implement `client.py` with env-driven init.
4. Implement each repository as a thin facade over Supabase queries.
5. Implement `Storage.store_raw` with the classification-gated branch.
6. Write `FakeSupabase` for tests.
7. Integration test: write one document + one biomarker record + one audit row; read them back.

## Acceptance criteria

- [ ] Migrations apply cleanly to a fresh Supabase project.
- [ ] All repositories pass unit tests against `FakeSupabase`.
- [ ] Integration test (env-gated) writes + reads through live Supabase.
- [ ] `Storage.store_raw` discards `not_supported` files and audits the discard.
- [ ] Every service call generates an audit row.
- [ ] No service outside `src/persistence/` imports `supabase`.

## Verification

- `pytest tests/persistence -q`
- `VITALOG_LIVE_SUPABASE=1 pytest tests/persistence/test_integration.py -q`
- `grep -r "from supabase" src/ | grep -v "src/persistence/"` — must be empty.
- Inspect Supabase dashboard: tables populated, storage bucket contains uploaded test docs.
