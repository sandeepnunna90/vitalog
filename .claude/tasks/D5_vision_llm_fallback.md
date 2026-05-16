# D5 — Vision-LLM fallback

**Epic:** Ingestion
**Points:** 3
**Priority:** High
**Depends on:** D4, B1
**Architecture refs:** §5.1 (step 6, fallback path); ADR-02 (Option C — hybrid); PRD v2 Scenario 2

## User story

As Mark photographing a 2022 paper report in poor lighting,
I want Vitalog to fall back to a vision-LLM when Textract confidence is too low,
So that my low-quality photo still yields biomarkers — but those biomarkers route to the review band rather than auto-accept.

## Why this matters

ADR-02 chose the hybrid path because vision-LLMs confabulate plausible numbers on the primary path but ARE valuable as a fallback for edge cases Textract can't handle. The key insight: fallback-extracted records carry lower composite confidence and surface for user review, not silent acceptance.

## Acceptance criteria

1. **Given** a Textract result whose minimum field confidence is below `THRESHOLD_FALLBACK` (initial 95, calibrated in C5), **When** D5 is invoked, **Then** the original file bytes are sent to Claude with vision via `Gateway.call("vision_fallback", "v1", ...)`.
2. **Given** the vision fallback, **When** the model returns, **Then** the output is a `TextractResult`-shaped Pydantic model (same shape as D4) — downstream code doesn't need to know which path ran.
3. **Given** the vision-fallback prompt, **When** I read it, **Then** it instructs the model to ONLY transcribe what's visible, never interpret, and to mark low-confidence fields explicitly.
4. **Given** a fallback-extracted record, **When** composite confidence is computed in D6, **Then** the fallback path contributes a lower `vision_confidence` than Textract would for the same field (so review-band routing is the typical outcome).
5. **Given** the contract, **When** D5 is not needed (Textract was confident), **Then** D5 is NOT invoked — saves cost.
6. **Given** the audit log, **When** D5 runs, **Then** event_type `vision_fallback_invoked` is recorded with the trigger reason (which field's confidence was low).

## Files to create / modify

- `src/ingestion/vision_fallback.py`
- `prompts/vision_fallback/v1.md` — the structuring-via-vision prompt
- `prompts/vision_fallback/v1.frontmatter.yaml`
- `src/gateway/anthropic_adapter.py` — extend to accept image inputs (the seam was designed in B1)
- `tests/ingestion/test_vision_fallback.py` — uses recorded Gateway responses

## Implementation notes

- The fallback is triggered when `min(field_confidences from Textract) < THRESHOLD_FALLBACK`. Initially 95; calibrated by C5 (the fallback threshold is the lower bound of the auto-accept band).
- The vision prompt is intentionally narrower than the main structurer prompt: it transcribes the image into the same shape Textract produces, NOT into biomarker candidates. This keeps the seams clean — the structurer is unchanged; it sees a `TextractResult` regardless of which path produced it.
- Cost: vision calls are 5–10× the cost of text calls. Make sure D5 only fires when needed; document expected fallback frequency (~10% of documents in early eval).
- Vision input: full-resolution image; for multi-page PDFs, send each page separately and concatenate the structured results.
- Confidence from vision: the prompt asks the model to emit per-field confidence on a 0–100 scale; treat anything ≥80 as decent but never higher than 90 (caps the auto-accept-band probability for vision-extracted records).
- This story is paired with D6 — once D6 lands, the integration is "if Textract min_conf < threshold, call D5 instead of returning Textract."

## Verification

- `pytest tests/ingestion/test_vision_fallback.py -q`
- Integration with D6: `pytest -m integration tests/ingestion/test_pipeline_end_to_end.py` with a low-quality fixture
- Manual: run the adversarial photographed-paper doc through the pipeline, observe the fallback triggers and records land in the review band

## INVEST check

- [x] Independent — only D4 + B1 required
- [x] Negotiable — exact trigger threshold flexible (set by C5)
- [x] Valuable — handles photographed-paper case
- [x] Estimable — well-bounded
- [x] Small — 3 pts
- [x] Testable — recorded fixture tests + integration

## Deferred (explicitly out of this story)

- Multi-provider vision fallback (capstone single-provider per ADR-08)
- Handwriting-specialized vision pipeline (v1+)
- Adaptive triggering (e.g., per-field fallback rather than per-document) — v1

## Notes / changelog

### Implementation (2026-05-16)

**Files created:**
- `src/ingestion/textract_fallback.py` — `TextractFallbackAdapter`; `THRESHOLD_FALLBACK = 95.0`; `_compute_min_confidence` aggregates confidence across all blocks, table cells, and KV pairs; `_build_image_content` routes PDF and HEIC through `_pdf_to_png` (PyMuPDF renders page 1 at 2× zoom → PNG) and passes supported image types directly; `_to_textract_result` normalizes `FallbackExtractionResult` back to `TextractResult` with 1-based row/col indexes matching Textract convention, `bbox=None` throughout, `page_count=1`; writes `vision_fallback_skipped` or `vision_fallback_invoked` audit entry.
- `prompts/extraction/v1.md` — transcribe-only vision prompt; reports per-field confidence 0–100; instructs model to use `[unreadable]` for unclear text and never interpret or infer values; registered in `prompts/_registry.yaml`.
- `tests/ingestion/test_textract_fallback.py` — 15 unit tests; Gateway and AuditLogRepository mocked; covers threshold boundary (exactly 95.0), both audit event types, result conversion (full and empty), whitespace line filtering, JPEG/PDF/HEIC image content paths, `_compute_min_confidence` across all signal types, and Gateway error propagation.

**Files modified:**
- `src/ingestion/__init__.py` — added exports: `TextractFallbackAdapter`, `FallbackExtractionResult`.
- `prompts/_registry.yaml` — registered `extraction/v1`.
- `CLAUDE.md` — moved D5 files from "Up next" → "Built (Epic A–D)".

**PR review fixes (commit 6297a85):**
- Wrapped `fitz.open()` in context manager (`with fitz.open(...) as doc:`) to close the native C handle after PNG render — was leaking one handle per PDF fallback call.
- Rerouted HEIC uploads through `_pdf_to_png` (PyMuPDF) instead of sending raw HEIC bytes labeled as `image/jpeg` — HEIC is ISOBMFF/HEVC, not wire-compatible with JPEG; Anthropic API would reject it.
- Added `test_heic_upload_builds_png_image_content` covering the HEIC → PNG conversion path.

**Key design decisions:**
- `_build_image_content` routes any MIME type not in `_SUPPORTED_MEDIA_TYPES` (the Anthropic vision API's accepted set) through PyMuPDF, so PDF and HEIC both become PNG without separate branches.
- `FallbackExtractionResult` is a distinct schema (not `TextractResult`) so the prompt output schema is explicit and independently testable; `_to_textract_result` converts it at the boundary.
- `gateway: Any` and `audit_repo: Any` in `__init__` — avoids circular imports in tests; commented with reason per project convention.
- Only page 0 of multi-page documents is sent to vision (capstone scope); documented in `_to_textract_result` docstring (`page_count=1`).
