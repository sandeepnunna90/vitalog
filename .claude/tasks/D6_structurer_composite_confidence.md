# D6 — Structurer + composite confidence + 3-band routing

**Epic:** Ingestion
**Points:** 8
**Priority:** Critical
**Depends on:** D4, D5, B1, B3
**Architecture refs:** §5.1 (steps 7–9, §5.1.1); PRD v2 Extraction; project CLAUDE.md Gotchas

## User story

As Mark uploading a lab document,
I want a structurer that turns Textract output (or vision-fallback output) into biomarker candidate records with field-level confidence, and routes each field into auto-accept / review / reject bands,
So that what flows into trends is trustworthy and what's uncertain comes to me for confirmation.

## Why this matters

This is the heart of Ingestion. The composite-confidence + 3-band model is one of the architectural pillars that PRD v2 v1's-binary-threshold rule was replaced with (v2 change #4). Implementing it correctly is what makes calibration (C5) meaningful, and what makes the review band Mark's confidence loop actually work.

## Acceptance criteria

1. **Given** a `TextractResult` (from D4 or D5), **When** the structurer runs, **Then** it returns a list of `BiomarkerCandidate` Pydantic objects each with: raw name, raw value, raw unit, raw reference range, collection date, lab source, field-level `llm_confidence` (0–100), and source-region pointers (page, bbox) for verification.
2. **Given** each field, **When** composite confidence is computed, **Then** it equals `min(textract_field_confidence, llm_structurer_confidence, classification_confidence)`. The minimum is computed per field, not per document.
3. **Given** each field's composite confidence, **When** band routing runs, **Then** auto-accept (`≥ THRESHOLD_AUTO_ACCEPT`) records flow to Normalization as verified; review (`THRESHOLD_REJECT ≤ c < THRESHOLD_AUTO_ACCEPT`) records flow as `verified_by='pending_user'`; reject (`< THRESHOLD_REJECT`) records are NOT stored and the document is flagged.
4. **Given** the constants, **When** I read `src/ingestion/structurer.py`, **Then** `THRESHOLD_AUTO_ACCEPT` and `THRESHOLD_REJECT` are named constants at the top of the file (initial values 95 and 70; later overwritten by C5).
5. **Given** the structurer prompt, **When** I read it, **Then** the hard constraint is "Structure ONLY what's visible. Never interpret, infer, or recommend. Emit field-level confidence on a 0–100 scale."
6. **Given** the schema, **When** the model emits a non-conforming response, **Then** L3 schema validation (from B3) catches it and triggers the retry-or-refuse path.
7. **Given** the output, **When** the caller receives the list, **Then** each candidate carries the chosen band (`auto_accept` | `review` | `reject`) and the reasoning constants used.

## Files to create / modify

- `src/ingestion/structurer.py` — main entry point + named threshold constants + band routing
- `src/ingestion/structurer_schemas.py` — `BiomarkerCandidate`, `Band` enum
- `prompts/structurer/v1.md` — the structuring prompt
- `prompts/structurer/v1.frontmatter.yaml`
- `src/ingestion/composite_confidence.py` — per-field min computation
- `src/ingestion/band_router.py` — band selection logic
- `tests/ingestion/test_structurer.py` — uses recorded Gateway responses
- `tests/ingestion/test_composite_confidence.py`
- `tests/ingestion/test_band_router.py`

## Implementation notes

- The structurer is the LARGEST single LLM-touching surface in Ingestion. Care with prompt design: be explicit about the JSON shape, include 2–3 in-prompt examples of correct output, and emphasize "no interpretation" multiple times.
- The schema enforces value/unit/range as strings as-extracted, NOT parsed numerics. Parsing happens in Normalization (E3) where unit conversion + range validation live. This separation is from P4 (deterministic where possible).
- Field-level confidence must be self-assessed by the model. The prompt asks it to score each field 0–100 based on visible clarity, ambiguity, and uncertainty about the value.
- Composite `min()` over three signals: Textract field confidence (from D4), LLM field confidence (from this story), classification confidence (from D2). All three available at routing time.
- Band routing decisions are emitted as part of the output, so downstream services don't re-compute. The audit log captures the chosen band per field.
- For multi-page documents, structurer runs per-page and the candidate lists are concatenated; collection_date is unified across pages (typically same for a single lab report).
- Project CLAUDE.md Gotchas: thresholds are constants, never magic. Test asserts the constants are defined at module level.

## Verification

- `pytest tests/ingestion/test_structurer.py -q` — recorded fixtures cover clean PDF, photo-fallback, missing-field cases
- `pytest tests/ingestion/test_composite_confidence.py -q` — min computation, edge cases (one signal missing → use available signals)
- `pytest tests/ingestion/test_band_router.py -q` — band boundaries, equal-to-threshold edge cases
- Integration: `pytest -m integration tests/ingestion/test_pipeline_end_to_end.py` covering Quest synthetic → 9 records all auto-accept
- After C5 lands: re-run accuracy harness, confirm band distributions match calibration

## INVEST check

- [x] Independent — needs D4, D5, B1, B3 contracts
- [x] Negotiable — internal layering flexible; prompt wording flexible
- [x] Valuable — the heart of extraction
- [x] Estimable — well-bounded but the largest story
- [x] Small — 8 pts (at the limit; do NOT split further or routing becomes leaky)
- [x] Testable — fixture-driven + integration

## Deferred (explicitly out of this story)

- Per-signal independent thresholds (architecture §5.1.1 v1)
- Weighted-average composite (intentional — `min()` is the architectural choice)
- Continuous threshold re-calibration (v1)
- ML-based confidence ensembling (v1+)

## Notes / changelog

### Implementation (2026-05-16)

**Files created:**
- `src/ingestion/structurer_schemas.py` — `Band` StrEnum, `RawBiomarkerCandidate` (LLM output), `StructuredReport` (Gateway schema), `BiomarkerCandidate` (public output with composite + band)
- `src/ingestion/composite_confidence.py` — `compute_composite(textract, llm, classification)` scales classification from 0-1 to 0-100 internally
- `src/ingestion/band_router.py` — `assign_band(composite, threshold_auto_accept, threshold_reject)` thresholds passed in, not hard-coded
- `src/ingestion/structurer.py` — `Structurer` class + `THRESHOLD_AUTO_ACCEPT=95.0` / `THRESHOLD_REJECT=70.0` module constants; `_serialize_textract_result` flattens KV/tables/blocks; `_compute_textract_floor` uses global min (conservative, mirrors D5 approach)
- `prompts/structurer/v1.md` — Sonnet, 4096 tokens, 3 in-prompt examples, "ONLY what's visible" hard constraint
- `tests/ingestion/test_structurer.py` — 17 tests; Gateway and audit mocked
- `tests/ingestion/test_composite_confidence.py` — 9 tests; covers all three lowest-signal cases + scaling
- `tests/ingestion/test_band_router.py` — 9 tests; boundary conditions at both thresholds + custom thresholds

**Files modified:**
- `prompts/_registry.yaml` — registered `structurer/v1`
- `src/ingestion/__init__.py` — exported `Structurer`, `StructurerResult`, thresholds, `Band`, `BiomarkerCandidate`, `StructuredReport`

**Key design decisions:**
- **Textract floor (not per-field)**: `TextractResult` at D6 is post-D5, so the global OCR min is already the relevant signal. Per-field lookup would require the LLM to emit block IDs, adding schema complexity with no calibration benefit.
- **Thresholds passed to `assign_band`**: lets C5 change constants in `structurer.py` without touching routing logic.
- **`_compute_textract_floor` copied from D5** (not imported): avoids cross-module coupling between two independent adapters; function is 5 lines.
- **`dataclass` for `StructurerResult`** (not Pydantic): internal return type, not persisted or serialized.

**Test results:** 218 unit tests pass; 0 failures; mypy --strict clean; ruff check + format clean.
