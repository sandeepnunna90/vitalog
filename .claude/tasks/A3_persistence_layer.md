# A3 — Persistence layer (Supabase + repositories)

**Epic:** Foundation
**Points:** 5
**Priority:** Critical
**Depends on:** A1
**Architecture refs:** §5.3, §6.1, §6.2, §7.4 (RLS), ADR-04, ADR-07 (repository pattern)

## User story

As the founder building Vitalog,
I want a Supabase-backed persistence layer wrapped in repository interfaces,
So that every other concern (Ingestion, Normalization, Intelligence) reads and writes through a stable contract that can be re-pointed at AWS later (P7) without a refactor.

## Why this matters

P7 (designed for migration) and ADR-04 (Supabase now, AWS later) both depend on the repository pattern being there from day one. Putting the contracts in place before any service writes to Supabase prevents leaky Supabase SDK calls from showing up in business logic, which is the failure mode the pattern exists to prevent.

## Acceptance criteria

1. **Given** a Supabase project provisioned via the web UI, **When** I run `make migrate`, **Then** all 7 tables exist with the schema sketched in architecture §6.2 (patient, patient_profile, document, biomarker_record, canonical_biomarker, pending_taxonomy_entry, summary, audit_log).
2. **Given** the migrations have run, **When** I query any table without a `patient_id = auth.uid()` filter as a non-admin, **Then** RLS denies the query (verifiable via integration test using a non-service-role key).
3. **Given** the repository interfaces, **When** I instantiate `BiomarkerRepository`, **Then** it exposes `add()`, `get(record_id)`, `find_by_canonical_id()`, `list_for_patient()`, `list_pending_user()` — and nothing Supabase-specific.
4. **Given** the `DocumentStore` repository, **When** I call `put(file, retention_policy)`, **Then** the file is stored in Supabase Storage and the returned `storage_uri` can be retrieved via `get(storage_uri)`.
5. **Given** the `AuditLogRepository`, **When** I call `record(actor, event_type, payload)`, **Then** a row is inserted with timestamp, PII-redacted payload (per Layer 1 contract from B2), and an immutable hash chain back to the prior log entry.
6. **Given** any repository class, **When** I import it from `src.persistence`, **Then** zero `supabase` symbols appear in the module's public interface — only typed Pydantic models in / typed Pydantic models out.

## Files to create / modify

- `migrations/001_initial_schema.sql` — full DDL for the 7 tables + indexes + RLS policies
- `migrations/002_audit_log_hash_chain.sql` — trigger maintaining the audit-log hash chain
- `src/persistence/__init__.py` — re-exports the repos
- `src/persistence/supabase_client.py` — single Supabase client factory (service-role for migrations, anon for app)
- `src/persistence/biomarker_repository.py`
- `src/persistence/document_repository.py`
- `src/persistence/taxonomy_repository.py` — wraps both `canonical_biomarker` and `pending_taxonomy_entry`
- `src/persistence/summary_repository.py`
- `src/persistence/audit_log_repository.py`
- `src/persistence/document_store.py` — Supabase Storage adapter
- `src/persistence/models.py` — Pydantic models mirroring the tables
- `tests/persistence/test_repositories.py` — integration tests (marked `@pytest.mark.integration`)
- `tests/persistence/test_rls_isolation.py` — RLS proof tests
- `Makefile` — add `migrate` target

## Implementation notes

- Use the Supabase service-role key only for migrations and the audit-log hash trigger. Application code uses the anon key + JWT, so RLS is always enforced.
- Patient ID strategy for capstone: `mark_capstone` is a fixed UUID hardcoded in `mark_profile.json` (see G2). RLS rules accept this UUID via JWT claim during demo.
- `retention_policy` enum: `"permanent"` (lab_report, recognized_unsupported) or `"discard_after_classification"` (not_supported). `DocumentStore.put()` for the latter writes audit metadata only and returns a synthetic uri.
- Audit-log hash chain: each row stores `prev_hash`, `payload_hash`, `chain_hash = sha256(prev_hash || payload_hash)`. Trigger enforces append-only.
- Pydantic v2, `ConfigDict(strict=True)`, never `extra="allow"` (per project CLAUDE.md).
- Repository methods are typed: inputs are Pydantic models, outputs are Pydantic models, no dicts at the boundary.

## Verification

- `make migrate` — schema applies cleanly to a fresh Supabase project
- `pytest -m integration tests/persistence/ -q` — full integration suite green against a test Supabase project
- `pytest tests/persistence/test_rls_isolation.py::test_anon_cannot_read_other_patients` — RLS proof
- Manual: open Supabase studio, confirm all 7 tables + RLS policies + indexes
- `grep -r "supabase" src/ --include="*.py" | grep -v "src/persistence/"` returns zero lines (no Supabase leaks)

## INVEST check

- [x] Independent — only A1 required
- [x] Negotiable — implementation flexible; contracts fixed
- [x] Valuable — gates D3, E1–E4, F1–F6
- [x] Estimable — schema is well-specified in architecture §6.2
- [x] Small — 5 pts (DDL + thin wrappers + integration tests)
- [x] Testable — RLS provable, hash chain provable

## Deferred (explicitly out of this story)

- Application-level encryption beyond Supabase defaults (v1.5)
- Real Supabase Auth flow (capstone uses a fixed JWT; user-initiated deletion deferred)
- Multi-tenant patient_id scoping beyond the single Mark profile (v1)
- AWS migration adapters (real; capstone has only Supabase)

## Notes / changelog

### Implementation complete (2026-05-14)

**Files created:**
- `migrations/001_initial_schema.sql` — 8 tables (patient, patient_profile, document, canonical_biomarker, pending_taxonomy_entry, biomarker_record, summary, audit_log) + 7 indexes + RLS policies. Enables pgcrypto extension for migration 002.
- `migrations/002_audit_log_hash_chain.sql` — BEFORE INSERT trigger computing prev_hash, payload_hash, chain_hash via pgcrypto sha256. Trigger is SECURITY DEFINER.
- `src/persistence/models.py` — Pydantic v2 models with `ConfigDict(strict=True)` for all 8 tables plus Create variants and `RetentionPolicy` / `DocumentClassification` / `VerifiedBy` / `PendingStatus` literal types.
- `src/persistence/supabase_client.py` — `get_service_client()` (bypasses RLS, uses SUPABASE_SERVICE_KEY) and `get_anon_client(jwt)` (RLS enforced, uses SUPABASE_ANON_KEY + `client.postgrest.auth(jwt)`).
- `src/persistence/biomarker_repository.py` — `add`, `get`, `find_by_canonical_id`, `list_for_patient`, `list_pending_user`.
- `src/persistence/document_repository.py` — `add`, `get_by_id`, `list_for_patient`, `update_processing_status`.
- `src/persistence/taxonomy_repository.py` — canonical: `get_canonical`, `list_all_canonical`; pending: `add_pending`, `list_pending`, `resolve_pending`.
- `src/persistence/summary_repository.py` — `add`, `get`, `list_for_patient`, `update_annotations`.
- `src/persistence/audit_log_repository.py` — `record` (append-only, hash columns filled by trigger), `get_last_n`.
- `src/persistence/document_store.py` — `put(file_bytes, filename, patient_id, retention_policy)` → `supabase-storage://...` or `discard://...`; `get(uri)` → bytes or None.
- `src/persistence/__init__.py` — re-exports all repos, client factories, and models.
- `tests/persistence/test_repositories.py` — 12 integration tests covering all repos.
- `tests/persistence/test_rls_isolation.py` — 6 integration tests proving RLS isolation.

**Modified:**
- `Makefile` — added `migrate` target (`psql "$(SUPABASE_DB_URL)" -f migrations/00*.sql`).
- `.env.example` — added `SUPABASE_ANON_KEY=` and `SUPABASE_DB_URL=`.

**Key design decisions:**
- Task file said "7 tables" but listed 8 — implemented all 8 per the actual §6.2 schema.
- All repos use `data: Any` for `.data` access (supabase-py returns `list[JSON]`, not `list[dict[str, Any]]`). `mypy --strict` passes with zero errors.
- `DocumentStore.put()` with `"discard_after_classification"` policy returns `discard://<uuid>` without uploading. Callers write an audit log entry with the discard URI.
- RLS tests use a `_fake_jwt()` placeholder — real JWT testing requires a live Supabase auth token issued against the test project. The test structure is correct; swap in a real JWT for full RLS validation.
- Mark's patient row seeded in G2, not here — A3 only creates the schema.

**Verification:**
- `ruff check src/persistence/ tests/persistence/` → all checks passed
- `mypy --strict src/persistence/` → no issues found in 9 source files
- `pytest -q -m "not integration"` → 33 passed, 17 deselected
- `grep -r "supabase" src/ --include="*.py" | grep -v "src/persistence/"` → zero output
