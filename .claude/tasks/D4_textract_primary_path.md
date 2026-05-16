# D4 — AWS Textract primary path

**Epic:** Ingestion
**Points:** 5
**Priority:** Critical
**Depends on:** D1
**Architecture refs:** §5.1 (steps 5–6); ADR-02; PRD v2 Extraction OCR strategy row

## User story

As Mark uploading a clean Quest PDF,
I want AWS Textract to extract the text, tables, and key-value pairs with per-field confidence,
So that the structurer works from auditable OCR output rather than a vision LLM that might confabulate plausible numbers.

## Why this matters

ADR-02 is one of the load-bearing architectural decisions for safety. Vision-LLM-direct hallucinates plausible numbers when source is ambiguous; Textract on text-extractable PDFs is mature, auditable, and table-aware. Putting this in the primary path eliminates a whole class of failure.

## Acceptance criteria

1. **Given** a text-extractable PDF, **When** Textract runs via `AnalyzeDocument(FeatureTypes=[FORMS, TABLES])`, **Then** the result contains the document text, table cells with row/col indexes, and KV pairs — all with per-element confidence (0–100).
2. **Given** an image (JPG/PNG), **When** Textract runs, **Then** the same result shape is returned (Textract is image-aware).
3. **Given** the Textract response, **When** the adapter normalizes it, **Then** the output conforms to a Pydantic `TextractResult` model with: `blocks` (text + bbox + confidence), `tables` (rows × cells with confidence), `kv_pairs` (key + value + confidence + bbox).
4. **Given** the adapter, **When** I call `extract(file)`, **Then** it accepts both PDF bytes and image bytes and dispatches to Textract's `analyze_document` synchronously (no async jobs for capstone — bounded doc sizes).
5. **Given** an AWS error (rate-limited, transient), **When** the adapter runs, **Then** it retries with exponential backoff up to 3 times and surfaces a typed `TextractFailureError` on persistent failure.
6. **Given** the audit-log requirement, **When** Textract runs, **Then** an audit entry of event_type `textract_extracted` is written with `document_id`, latency, min_confidence, max_confidence, table_count, kv_count.

## Files to create / modify

- `src/ingestion/textract_adapter.py`
- `src/ingestion/textract_schemas.py` — Pydantic `TextractResult`, `Block`, `Table`, `KVPair`
- `src/ingestion/errors.py` — add `TextractFailureError`
- `tests/ingestion/test_textract_adapter.py` — uses recorded Textract responses (no live AWS for unit tests)
- `tests/ingestion/fixtures/textract_responses/` — recorded fixtures

## Implementation notes

- Use `boto3` with the credentials from `.env`. The AWS region is read from `AWS_REGION` env var, default `us-east-1`.
- Free tier covers ~1000 pages/month — capstone doc volume is bounded well under that, document this in `runs/cost_notes.md`.
- The adapter normalizes Textract's verbose response into our Pydantic schema. Downstream services never see boto3 types.
- Tables: Textract returns cells; the adapter reconstructs row-major matrices for downstream consumption by the structurer prompt.
- KV pairs: Textract returns separate KEY and VALUE blocks linked by relationships; the adapter resolves these into a clean `{key, value, confidence}` list.
- The `min_confidence` from the audit log is the value that feeds into the fallback decision in D5 (compared against `THRESHOLD_FALLBACK`).
- For integration tests, mark with `@pytest.mark.integration` and use a tiny fixture PDF; ensure CI does NOT run these.

## Verification

- `pytest tests/ingestion/test_textract_adapter.py -q` — unit tests against recorded fixtures
- Integration: `pytest -m integration tests/ingestion/test_textract_adapter.py` — runs against a tiny real PDF
- Manual: process a Quest synthetic from C1, confirm tables and KV pairs land correctly in the normalized output

## INVEST check

- [x] Independent — only D1 required
- [x] Negotiable — implementation flexible
- [x] Valuable — gates D6 + the entire ingestion pipeline
- [x] Estimable — well-bounded boto3 integration
- [x] Small — 5 pts
- [x] Testable — fixture-driven unit tests + small integration test

## Deferred (explicitly out of this story)

- Async Textract jobs for large documents (v1; capstone doc sizes are bounded)
- Custom Textract analyzers / queries (v1 if needed)
- Multi-region Textract (v2+)

## Notes / changelog

### Implementation (2026-05-16)

**Files created:**
- `src/ingestion/textract_schemas.py` — `BoundingBox`, `Block`, `TableCell`, `Table`, `KVPair`, `TextractResult` Pydantic models; all confidence fields annotated with `# Textract-native 0–100 scale` comment (D6 structurer must normalize to 0–1 before computing composite confidence).
- `src/ingestion/textract_adapter.py` — `TextractAdapter`; deferred `import boto3` inside `__init__` (avoids import-time AWS SDK overhead); `client: Any | None = None` injection parameter for test isolation (mirrors `AnthropicAdapter` pattern); `_call_textract` (retry wrapper) and `_normalize` (response parser) kept separate for independent testability; `NoCredentialsError` caught before `BotoCoreError` — config errors fail immediately without burning retry slots; `_to_row_matrix` builds row-major matrix from Textract's flat CELL list; merged-cell silent overwrite documented as known capstone limitation.
- `tests/ingestion/test_textract_adapter.py` — 12 unit tests + 1 integration test (skips if `AWS_ACCESS_KEY_ID` unset); all boto3 mocked via `client=` injection; inline Textract response dicts (no committed binaries); `patch` calls scoped to `src.ingestion.textract_adapter.time.sleep`.
- `runs/cost_notes.md` — Textract free-tier cost note; capstone demo volume (~10 docs) well under 1,000 pages/month free limit.

**Files modified:**
- `src/ingestion/errors.py` — added `TextractFailureError(reason, attempt_count)`.
- `src/ingestion/__init__.py` — added exports: `TextractAdapter`, `TextractResult`, `TextractFailureError`.

**PR review fixes (commit 71db89c):**
- Added comment to `cell_map[(row_idx, col_idx)] = TableCell(...)` documenting merged-cell silent overwrite as known capstone limitation (same pattern as D3 orphaned-storage gap).
- Added `# Textract-native 0–100 scale` to all confidence fields in `textract_schemas.py` (not just `Block.confidence`).
- Scoped `patch("time.sleep")` → `patch("src.ingestion.textract_adapter.time.sleep")` in retry tests.
- Added `test_retry_on_boto_core_error` covering connection-level `BotoCoreError` retry path.

**Key design decisions:**
- Synchronous `analyze_document` call (no async Textract jobs) — bounded capstone doc sizes make async unnecessary; deferred to v1 per task spec.
- `min_confidence` in `textract_extracted` audit entry is the exact value D5 compares against `THRESHOLD_FALLBACK` to decide whether to run the vision-LLM fallback.
- `TextractResult` is the contract between D4 and D6 — downstream structurer never sees raw boto3 dicts.
- Confidence values preserved in Textract's native 0–100 scale; normalization to 0–1 is D6's responsibility.
