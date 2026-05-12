# Task 05 — Textract client

## Context

Per architecture ADR-02, AWS Textract is the primary OCR path; vision-LLM is fallback only. The LLM never sees the document image on the primary path. Textract returns text + tables + KV pairs with per-block confidence — this task wraps the SDK call, normalizes the response, and computes per-field Textract confidence that flows into composite confidence at task 07.

## Dependencies

- Task 00 (repo bootstrap — boto3 dependency)
- Task 01 (schemas — `ExtractionField`)
- Task 03 (eval corpus — fixtures + the one low-quality synthetic that exercises confidence floors)

## In scope

`src/ingestion/textract_client.py`:

- `TextractClient.analyze(document_bytes: bytes) -> TextractResult`:
  - Calls `AnalyzeDocument` with `FeatureTypes=["TABLES", "FORMS"]`.
  - Parses response into a normalized internal model: `TextractResult(text_blocks, tables, kv_pairs, page_confidences, avg_field_confidence)`.
  - Each block carries Textract's `Confidence` (0–100).
- Local mocking strategy: ship a `tests/fixtures/textract_response.json` taken from one real Textract call against a hero PDF, and a `FakeTextractClient` for unit tests.
- `THRESHOLD_FALLBACK` constant (initial 60) — task 06 uses this to decide when to invoke vision fallback.
- Cost-awareness: log per-call page count + estimated cost via eval logger.

## Out of scope (deferred)

- Handwriting-specific features (`Textract.AnalyzeDocument FeatureTypes=["SIGNATURES"]`) — v1.
- Asynchronous batch jobs (use sync `AnalyzeDocument` for capstone single-page focus).
- Cross-page table reconciliation (Quest reports fit on 1–2 pages).
- Production retries / backoff (basic retry is fine; full circuit-breaking deferred).

## Files to create

- `src/ingestion/textract_client.py`
- `src/ingestion/textract_models.py` — internal normalized `TextractResult` dataclass (kept distinct from `BiomarkerCandidate` which is post-structurer).
- `tests/ingestion/test_textract_client.py`
- `tests/fixtures/textract_response.json` (real response captured against one hero PDF, sanitized)

## Architecture references

- `docs/Vitalog_architecture.md` ADR-02 — OCR strategy
- `docs/Vitalog_architecture.md` §5.1 — Ingestion pipeline
- `docs/Vitalog_PRD_v2.md` §Functional Requirements "Extraction → OCR strategy"

## Step-by-step

1. Set up AWS creds (use `~/.aws/credentials` profile `vitalog-dev`, region `us-east-1`).
2. Capture one real Textract response against a hero PDF; save as fixture.
3. Sanitize the fixture (no real patient data — but our hero data is synthetic so this is fine).
4. Implement `TextractClient.analyze` against the live SDK.
5. Implement `FakeTextractClient` that returns the fixture; use it in unit tests.
6. Add `THRESHOLD_FALLBACK` constant in `src/ingestion/thresholds.py` (so it can be tuned in one place).
7. Integration test: call live Textract against one hero PDF behind env flag `VITALOG_LIVE_AWS=1`.

## Acceptance criteria

- [ ] Unit tests run with `FakeTextractClient`; no AWS calls.
- [ ] Integration test (env-gated) hits real Textract once and matches expected biomarker count.
- [ ] `TextractResult.avg_field_confidence` correctly computed from per-block confidences.
- [ ] Cost estimate logged per call.
- [ ] `mypy src/ingestion --strict` clean.

## Verification

- `pytest tests/ingestion/test_textract_client.py -q`
- `VITALOG_LIVE_AWS=1 pytest tests/ingestion/test_textract_client.py::test_live -q` — runs once, confirms live call works.
- Tail eval logger to confirm one log line per analyze call.
