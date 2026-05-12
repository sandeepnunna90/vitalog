# Task 04 — Document classifier

## Context

Classification is the first decision in the ingestion pipeline. Three top-level categories (architecture §5.1): `lab_report` → extraction pipeline, `recognized_unsupported` → store-only with v1+ message, `not_supported` → discard with audit-only. Rich subtype is captured for future v1 expansion but routing decisions use top-level only.

## Dependencies

- Task 01 (schemas — `ClassificationResult`, `DocumentCategory`)
- Task 02 (AI Gateway — classifier prompt routes through Gateway)
- Task 03 (eval corpus — classification ground truth in `manifest.json`)

## In scope

`src/ingestion/classifier.py`:

- `Classifier.classify(raw_document: RawDocument) -> ClassificationResult`.
- Pre-LLM probes (fast-reject without an LLM call):
  - Empty file → `not_supported`.
  - Corrupted PDF / unreadable → `not_supported`.
  - Zero text after `pdfminer` first-page extraction → `not_supported`.
- If probes pass, extract first-page text snippet (~500 chars) and pass to Gateway.
- `prompts/classifier/v1.md` — instructs the model to return `ClassificationResult`. Includes few-shot examples for each category (use eval corpus docs as fixtures).
- Conservative bias: instruct model to default to `not_supported` under uncertainty. Restate in system preamble.
- Subtype taxonomy enumerated in the prompt (full v1 list) but only top-level category drives routing.

## Out of scope (deferred)

- Per-subtype routing (v1 — architecture §5.1 deferred classification work).
- Image content moderation (v1).
- Multi-page classification (single-page check is sufficient for capstone).

## Files to create

- `src/ingestion/classifier.py`
- `src/ingestion/probes.py` (the fast-reject probes — kept separate so they're testable without LLM mocks)
- `prompts/classifier/v1.md`
- `tests/ingestion/test_classifier.py` (uses eval corpus + mocked Gateway)
- `tests/ingestion/test_probes.py`

## Architecture references

- `docs/Vitalog_architecture.md` §5.1 — Ingestion + classification table
- `docs/Vitalog_architecture.md` §5.1 "Pre-LLM probes" section
- `docs/Vitalog_PRD_v2.md` §Functional Requirements "Document Upload → Classification"
- `docs/vitalog_roadmap.md` §4 Ingestion (three-category, conservative bias)

## Step-by-step

1. Implement probes first — they're pure functions, easy to test.
2. Write `prompts/classifier/v1.md` with category definitions, subtype list, few-shot examples, conservative-bias instruction.
3. Implement `Classifier.classify` that wires probes → Gateway → result.
4. Build test fixtures from eval corpus: one document per (category, subtype) combination.
5. Mock Gateway in unit tests; integration tests can hit a real model behind an env flag.
6. Measure classification accuracy against `manifest.json` ground truth; record in `EVAL_RESULTS.md`.

## Acceptance criteria

- [ ] `pytest tests/ingestion/test_classifier.py -q` — green with mocked Gateway.
- [ ] All probes have unit tests with edge inputs (empty bytes, corrupt PDF, image-only).
- [ ] Running the classifier against eval corpus achieves ≥90% top-level accuracy on the 12 synthetic docs.
- [ ] No false negatives on `not_supported` examples — bias is conservative.
- [ ] Subtype field populated even when routing uses top-level only.

## Verification

- `pytest tests/ingestion -q`
- `python -m src.ingestion.classifier eval_corpus/synthetic/*.pdf` — prints `(filename, category, subtype, confidence)` for each.
- Compare output to `eval_corpus/manifest.json`; flag mismatches.
