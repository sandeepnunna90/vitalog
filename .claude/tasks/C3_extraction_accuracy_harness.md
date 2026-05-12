# C3 — Extraction accuracy harness

**Epic:** Eval Corpus & Harness
**Points:** 3
**Priority:** High
**Depends on:** C2
**Architecture refs:** §11 (Eval suite); PRD v2 Testing & Measurement; architecture Appendix D

## User story

As the founder building Vitalog,
I want a harness that runs the full extraction pipeline against every doc in the eval corpus and emits per-field precision/recall against ground truth,
So that any prompt change ships with quantitative regression evidence rather than vibes.

## Why this matters

P6 (eval-driven development) requires measurement, not estimation. The harness is what makes the threshold rollback criteria in PRD v2 (≥85% on photographed reports, etc.) enforceable. It's also the input to C5 calibration.

## Acceptance criteria

1. **Given** the corpus + the full extraction pipeline (D1–D6), **When** I run `python scripts/run_accuracy.py --corpus eval_corpus/`, **Then** a report is emitted with per-doc, per-field results: extracted vs ground-truth value, unit, date, name, range.
2. **Given** the per-field results, **When** the harness aggregates, **Then** it reports precision, recall, F1 per field type (name, value, unit, range, date) across the full corpus.
3. **Given** the per-doc results, **When** the harness aggregates by split, **Then** it reports separate numbers for `synthetic`, `redacted_real`, `adversarial`.
4. **Given** the per-doc results, **When** the harness aggregates by confidence band, **Then** it reports accuracy within `auto_accept` / `review` / `reject` bands (input to C5 calibration).
5. **Given** the report, **When** I open `eval_corpus/runs/<timestamp>/accuracy.json` and `accuracy.md`, **Then** the JSON is machine-readable and the markdown is human-skimmable.
6. **Given** any prompt change to the structurer or classifier, **When** the harness runs, **Then** results are appended to a `history.csv` so regressions are visible across runs.

## Files to create / modify

- `scripts/run_accuracy.py` — CLI entry point
- `src/eval/harness/__init__.py`
- `src/eval/harness/runner.py` — orchestrates pipeline runs against the corpus
- `src/eval/harness/comparator.py` — per-field comparison (value with ±0.5% tolerance, unit exact, date exact, name fuzzy)
- `src/eval/harness/aggregator.py` — precision/recall/F1
- `src/eval/harness/reporter.py` — emits JSON + markdown
- `eval_corpus/runs/.gitkeep`
- `tests/eval/test_harness_comparator.py`

## Implementation notes

- Comparator tolerances mirror Mode B: ±0.5% on decimals, exact on integers, exact on units, exact on dates, fuzzy on names (use `rapidfuzz` ratio ≥ 90).
- Run output goes to `eval_corpus/runs/<timestamp>/`; `runs/` is gitignored (per A1 `.gitignore`).
- The harness DOES make Textract + Anthropic calls — it's the real pipeline. Mark as `@pytest.mark.integration` and document the cost (~$1–2 per full run).
- `history.csv` schema: timestamp, git_sha, prompt_versions_json, per-field-F1 columns. Append-only.
- For docs with classification ≠ `lab_report`, the harness records "classified as X, expected X" and does NOT attempt extraction — those are scored by the classification accuracy column instead.

## Verification

- `pytest tests/eval/test_harness_comparator.py -q` (mocked pipeline)
- `python scripts/run_accuracy.py --corpus eval_corpus/ --dry-run` — exercises the harness against ground truth only (no pipeline), confirms the report shape
- After D6 lands: full live run, inspect markdown report

## INVEST check

- [x] Independent — only C2 required
- [x] Negotiable — exact metric set flexible
- [x] Valuable — gates C5 calibration and any prompt change
- [x] Estimable — well-bounded
- [x] Small — 3 pts
- [x] Testable — comparator is unit-testable in isolation

## Deferred (explicitly out of this story)

- Per-vendor breakdown beyond Quest (v1)
- Real-time accuracy dashboard (v1)
- Per-user accuracy tracking (v1.5)

## Notes / changelog

_(append after work is done)_
