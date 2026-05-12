# Task 06 — Vision-LLM fallback

## Context

When Textract average field confidence falls below `THRESHOLD_FALLBACK` (60), the ingestion pipeline reroutes to a vision-LLM path: pass page images directly to Claude with vision. Per architecture ADR-02, this is the *only* path where the LLM sees the raw document, and the output shape must match the Textract path so the structurer is path-agnostic.

## Dependencies

- Task 02 (Gateway — vision call routes through Gateway with a vision-specific prompt)
- Task 03 (eval corpus — at least one intentionally low-quality synthetic that triggers fallback)
- Task 05 (Textract client — confidence check is the trigger)

## In scope

`src/ingestion/vision_fallback.py`:

- `VisionFallback.extract(document_bytes: bytes) -> TextractResult`:
  - Render PDF pages to PNG (or extract embedded images for image uploads) via `pypdfium2` or `pdf2image`.
  - Call Gateway with `prompts/vision_extractor/v1.md` and image content blocks.
  - Model returns the same `TextractResult` shape (text blocks, tables, KV pairs, confidences).
  - Confidences from vision path use the LLM's self-reported confidence (with a documented cap — e.g., never > 90 to reflect the higher uncertainty).
- `src/ingestion/router.py` — small dispatcher: take a `RawDocument`, run Textract, check `avg_field_confidence < THRESHOLD_FALLBACK`, dispatch to fallback. Returns a `TextractResult` regardless of path plus a `path_taken: Literal["textract", "vision"]` flag for observability.

## Out of scope (deferred)

- Handwritten-text optimization (v1).
- Multi-page documents > 5 pages (limit input size for capstone).
- Per-page confidence routing (route at document level for capstone).

## Files to create

- `src/ingestion/vision_fallback.py`
- `src/ingestion/router.py`
- `prompts/vision_extractor/v1.md`
- `tests/ingestion/test_vision_fallback.py`
- `tests/ingestion/test_router.py`

## Architecture references

- `docs/Vitalog_architecture.md` ADR-02 — OCR strategy
- `docs/Vitalog_architecture.md` §5.1 — Ingestion routing
- `docs/Vitalog_PRD_v2.md` §Functional Requirements "Extraction → Image/scan", §User Flow step 6

## Step-by-step

1. Implement PDF → image rendering (use `pypdfium2` — faster than pdf2image and no system deps).
2. Write `prompts/vision_extractor/v1.md` — same expected output shape as Textract, instructs LLM to populate confidence per field.
3. Implement `VisionFallback.extract`.
4. Implement `router.route(document)` with the threshold check.
5. Test: feed the low-quality hero synthetic; assert `path_taken == "vision"`.
6. Test: feed a high-quality hero synthetic; assert `path_taken == "textract"`.

## Acceptance criteria

- [ ] Both paths return identically-shaped `TextractResult`.
- [ ] Low-quality fixture triggers vision path; high-quality does not.
- [ ] Vision confidences capped at 90 (documented in code comment).
- [ ] `router.route` logs which path was taken to the eval logger.
- [ ] `mypy src/ingestion --strict` clean.

## Verification

- `pytest tests/ingestion/test_vision_fallback.py tests/ingestion/test_router.py -q`
- Manual: `python -m src.ingestion.router eval_corpus/synthetic/low_quality_*.pdf` → `vision`
- Manual: `python -m src.ingestion.router eval_corpus/synthetic/hero_*.pdf` → `textract`
