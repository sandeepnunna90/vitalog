# Task 07 — LLM Structurer + composite confidence + three-band routing

## Context

The Structurer takes `TextractResult` (from either path), calls the LLM to produce `BiomarkerCandidate[]`, computes composite confidence per field as `min(textract_field, llm_field, classification)`, and assigns each record to one of three bands: auto-accept / review / reject. This is the last ingestion step before normalization.

## Dependencies

- Task 01 (schemas — `BiomarkerCandidate`, `ExtractionField`, `ConfidenceBand`, `RoutingDecision`)
- Task 02 (Gateway — structurer prompt)
- Task 03 (eval corpus — ground truth for accuracy measurement)
- Task 04 (classifier — provides classification confidence for the `min()` calculation)
- Task 05 / 06 (Textract / vision — provide raw OCR confidence)

## In scope

`src/ingestion/structurer.py`:

- `Structurer.structure(textract_result, classification) -> List[BiomarkerCandidate]`:
  - Calls Gateway with `prompts/structurer/v1.md`, passing the Textract text + tables.
  - LLM returns biomarker candidates with field-level confidence (0–100).
  - For each field, composite = `min(textract_field_conf, llm_field_conf, classification_conf)`.
  - Hard constraint in prompt: structure only what is visible; never interpret, never recommend, never infer.
- `src/ingestion/thresholds.py`:
  - `THRESHOLD_AUTO_ACCEPT = 95` (default; calibrated by task 10)
  - `THRESHOLD_REJECT = 70`
  - `THRESHOLD_FALLBACK = 60` (already defined in task 05)
- `src/ingestion/router_bands.py` — `band_for(confidence: int) -> ConfidenceBand`. Returns `AUTO_ACCEPT` / `REVIEW` / `REJECT`.
- `src/ingestion/pipeline.py` — top-level orchestrator: `Pipeline.ingest(raw_doc) -> IngestionResult`. Glues classifier → router (textract/vision) → structurer → banding. Returns the full pipeline outcome including audit events.

## Out of scope (deferred)

- Per-signal independent thresholds (architecture §12 / roadmap §4 → v1).
- Continuous re-calibration in production (v1).
- DB writes (task 08).

## Files to create

- `src/ingestion/structurer.py`
- `src/ingestion/thresholds.py`
- `src/ingestion/router_bands.py`
- `src/ingestion/pipeline.py`
- `prompts/structurer/v1.md`
- `tests/ingestion/test_structurer.py`
- `tests/ingestion/test_router_bands.py`
- `tests/ingestion/test_pipeline.py` (end-to-end with mocked Gateway + Textract)

## Architecture references

- `docs/Vitalog_architecture.md` §5.1 — Ingestion + structurer
- `docs/Vitalog_architecture.md` §5.1.1 — Confidence band model
- `docs/Vitalog_architecture.md` Appendix D — calibration methodology
- `docs/Vitalog_PRD_v2.md` §User Flow steps 5–8
- `docs/Vitalog_PRD_v2.md` §Functional Requirements "Extraction → Clean PDF", "Extraction → Confidence bands"

## Step-by-step

1. Write `prompts/structurer/v1.md` with strict output schema (uses tool-use on `BiomarkerCandidate[]`).
2. Implement `band_for` — pure function, easy to test.
3. Implement composite confidence (`min`) — pure function.
4. Implement `Structurer.structure` — Gateway call + composite computation.
5. Implement `Pipeline.ingest` end-to-end.
6. Integration test: run pipeline against 3 hero docs; verify auto-accept count matches expectations.

## Acceptance criteria

- [ ] `pytest tests/ingestion -q` — green.
- [ ] Composite confidence is correctly `min(textract, llm, classification)`.
- [ ] Bands correctly assigned at boundaries (95 → AUTO_ACCEPT, 94 → REVIEW, 70 → REVIEW, 69 → REJECT).
- [ ] Pipeline returns audit events for every routing decision.
- [ ] Running pipeline against 3 hero docs yields ≥27 biomarker candidates (~9 per doc).
- [ ] Extraction accuracy on hero docs ≥95% per-field against ground truth.

## Verification

- `pytest tests/ingestion -q`
- `python -m src.ingestion.pipeline eval_corpus/synthetic/hero_*.pdf` — prints routing summary
- Compare extracted biomarkers to ground-truth JSON; report match rate
