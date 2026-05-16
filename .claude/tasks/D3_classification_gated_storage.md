# D3 — Classification-gated raw doc storage

**Epic:** Ingestion
**Points:** 3
**Priority:** Critical
**Depends on:** D1, D2, A3
**Architecture refs:** §7.6; PRD v2 Compliance/Privacy/Legal

## User story

As Mark uploading any document,
I want lab reports retained, recognized-but-unsupported docs retained with a roadmap message, and non-medical content (accidental photos, receipts) discarded after classification,
So that random personal content never accumulates on Vitalog's servers and my medical record stays clean.

## Why this matters

Classification-gated storage is the architectural answer to a privacy concern that the v1 PRD's blanket "never delete" rule would have created. §7.6 explicitly supersedes the prior rule. Getting this right at capstone time means no privacy debt has to be unwound later.

## Acceptance criteria

1. **Given** a classification result of `lab_report`, **When** D3 runs, **Then** the raw file is stored via `DocumentStore.put(file, retention_policy="permanent")` and a `document` row is inserted.
2. **Given** a classification result of `recognized_unsupported`, **When** D3 runs, **Then** the raw file is stored via `DocumentStore.put(file, retention_policy="permanent")`, a `document` row is inserted, AND a user-facing roadmap message is returned ("This looks like a {subtype} — …").
3. **Given** a classification result of `not_supported`, **When** D3 runs, **Then** the raw file is DISCARDED (never written to Storage), only audit metadata is recorded (filename, MIME, size, timestamp, classification result, confidence), and a generic rejection message is returned.
4. **Given** any classification outcome, **When** D3 runs, **Then** an audit-log entry of the appropriate event_type (`document_uploaded` | `document_classified_unsupported` | `document_classified_not_supported`) is written.
5. **Given** the `not_supported` path, **When** I check Supabase Storage, **Then** there is no object corresponding to that upload — only the audit row.
6. **Given** the contract, **When** Ingestion's pipeline branches on classification, **Then** the `recognized_unsupported` and `not_supported` paths short-circuit BEFORE Textract or the structurer are called (cost discipline).

## Files to create / modify

- `src/ingestion/storage_router.py` — central dispatch based on classification
- `src/ingestion/orchestration_hook.py` — short-circuit logic for non-lab_report classifications
- `src/persistence/document_store.py` — extend `put()` to honor `retention_policy`
- `tests/ingestion/test_storage_router.py`
- `tests/ingestion/test_short_circuit.py`

## Implementation notes

- `DocumentStore.put(file, retention_policy="discard_after_classification")` must NOT write to Storage. Instead it writes an audit metadata row with a synthetic uri (`audit-only://<hash>`) and returns that uri.
- Audit metadata for `not_supported`: filename, MIME, size, sha256(content), timestamp, classification_result, classification_confidence, subtype. Note: NOT the content. The content is gone.
- The short-circuit is in the orchestration layer (not in the value-layer services). Service D2 returns a ClassificationResult; orchestration decides whether to call Textract next.
- Message templates from D2 are reused — D3 is the integration point that returns them to the caller via Orchestration.
- This story is the answer to PRD v2 Scenarios 9 (discharge summary) and 10 (personal photo). Make sure both scenarios are covered by tests.

## Verification

- `pytest tests/ingestion/test_storage_router.py -q`
- `pytest tests/ingestion/test_short_circuit.py -q` — proves Textract is not called for non-lab_report classifications
- Integration: upload a known-not_supported doc, query Supabase Storage by hash, confirm no object exists
- Audit verification: every test asserts the correct audit-log event_type was written

## INVEST check

- [x] Independent — needs D1, D2, A3 contracts
- [x] Negotiable — exact message wording flexible
- [x] Valuable — privacy guarantee
- [x] Estimable — well-bounded
- [x] Small — 3 pts
- [x] Testable — branch coverage on all 3 categories

## Deferred (explicitly out of this story)

- Per-subtype storage policies (e.g., consent-prompt before storing genetic data) — v1
- Image content moderation for inappropriate uploads — v1
- User-initiated deletion of stored documents — v1
- Application-level encryption beyond Supabase defaults — v1.5

## Notes / changelog

### Implementation (2026-05-16)

**Files created:**
- `src/ingestion/storage_router.py` — `StorageRouteResult` Pydantic model + `StorageRouter` class; three private routing methods (`_route_lab_report`, `_route_recognized_unsupported`, `_route_not_supported`); `not_supported` path calls `store.put` with `"discard_after_classification"` (returns `discard://` URI, no Storage upload) and skips `doc_repo.add` entirely; `reasoning` truncated to 500 chars in audit payload; audit event types: `document_uploaded` / `document_classified_unsupported` / `document_classified_not_supported`.
- `src/ingestion/orchestration_hook.py` — `IngestionResult` Pydantic model + `IngestionOrchestrator`; wires `UploadValidator → DocumentClassifier → StorageRouter`; `textract_fn: Callable | None` slot for D4; short-circuit enforced via `should_continue_pipeline` flag; explicit `RuntimeError` guard replaces `assert` on `document_id`.
- `tests/ingestion/test_storage_router.py` — 14 tests covering all three branches, audit event types, PRD Scenarios 9 (discharge summary) and 10 (personal photo), and 3 error-path tests (`store.put` raises, `doc_repo.add` raises after put, reasoning truncation).
- `tests/ingestion/test_short_circuit.py` — 4 tests proving `textract_fn` is called only for `lab_report`.

**Files modified:**
- `src/ingestion/__init__.py` — added exports: `StorageRouter`, `StorageRouteResult`, `IngestionOrchestrator`, `IngestionResult`.

**PR review fixes (commit 6ad82bd):**
- Replaced `assert route.document_id is not None` with explicit `RuntimeError` check — `assert` is stripped by Python `-O` mode.
- Added code comment in `_route_lab_report` documenting partial-failure gap (orphaned Storage object if `doc_repo.add` raises after `store.put` succeeds) as a known capstone limitation.
- Truncated `result.reasoning` to `[:500]` in `not_supported` audit payload to avoid storing paraphrased file content in the append-only audit log.
- Added 3 error-path tests covering the failure modes.

**Key design decisions:**
- `StorageRouteResult.should_continue_pipeline` decouples routing logic from orchestration — the orchestrator doesn't branch on `Category`, only on this flag. D4 plugs in via `textract_fn` without touching the orchestrator's branching logic.
- `not_supported` documents produce **no** `DocumentRow` — only an audit entry. This is the hard enforcement of the §7.6 privacy guarantee.
- `recognized_unsupported` documents get `processing_status="complete"` (pipeline is done for them); `lab_report` gets `"pending"` (Textract runs next in D4).
- Partial-failure handling (orphaned Storage objects) deferred to post-capstone; documented in code comment and test docstring.
