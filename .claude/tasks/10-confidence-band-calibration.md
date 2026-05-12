# Task 10 — Confidence band calibration

## Context

Per architecture Appendix D, `THRESHOLD_AUTO_ACCEPT` and `THRESHOLD_REJECT` should be calibrated against the eval corpus rather than fixed at the defaults (95/70). For the 10-day capstone, this is a time-boxed grid search — 2 hours max. If the small corpus is inconclusive, ship defaults and document the limitation.

## Dependencies

- Task 03 (eval corpus + ground truth)
- Task 07 (pipeline produces composite confidence)
- Task 09 (normalization closes the loop so we can compare normalized records to ground truth)

## In scope

`scripts/calibrate_bands.py`:

- Grid: `THRESHOLD_AUTO_ACCEPT ∈ {90, 92, 95, 97, 99}` × `THRESHOLD_REJECT ∈ {60, 65, 70, 75, 80}`.
- For each pair:
  1. Run full ingestion + normalization pipeline against eval corpus with these thresholds.
  2. Compare resulting records to ground truth.
  3. Compute: precision in auto-accept band (fraction of auto-accepted that are correct), recall (fraction of correct that get auto-accepted), review-band size, reject-band size.
- Produce `eval_corpus/calibration_report.md` with a table of all 25 pairs and a recommended pair.
- If a non-default pair clearly dominates (better precision AND comparable recall), update `THRESHOLD_AUTO_ACCEPT` / `THRESHOLD_REJECT` constants in `src/ingestion/thresholds.py`. Otherwise, ship defaults with a note in the report.

## Out of scope (deferred)

- Per-signal independent thresholds (Textract / LLM / classification each calibrated separately) — v1.
- Continuous re-calibration in production — v1.
- Stratification by document type or vendor — v1.

## Files to create

- `scripts/calibrate_bands.py`
- `eval_corpus/calibration_report.md` (output, regenerated each run)
- `tests/scripts/test_calibrate_bands.py` — smoke test against a 2-doc subset to keep the test fast.

## Architecture references

- `docs/Vitalog_architecture.md` Appendix D — calibration methodology
- `docs/Vitalog_architecture.md` §5.1.1 — three-band model
- `docs/Vitalog_PRD_v2.md` §Testing & Measurement — calibration as week-2 activity

## Step-by-step

1. Implement pipeline-runner helper that lets you pass thresholds as args.
2. Iterate the 25-pair grid; cache pipeline results per-document so iteration is fast (don't re-run Gateway calls; cache the structured output and just re-band).
3. Compute the metrics above per pair.
4. Render `calibration_report.md` with table + recommendation.
5. Optional: update `thresholds.py` if a clear winner emerges.

## Acceptance criteria

- [ ] `python scripts/calibrate_bands.py` completes in < 5 minutes (using cached pipeline output).
- [ ] `calibration_report.md` exists with all 25 pairs + recommendation.
- [ ] Report explicitly states whether defaults were retained and why.
- [ ] If thresholds changed, the change is reflected in `src/ingestion/thresholds.py` AND `EVAL_RESULTS.md`.

## Verification

- `python scripts/calibrate_bands.py --use-cache`
- Open `eval_corpus/calibration_report.md`; spot-check one metric calculation by hand.
- Confirm thresholds in `src/ingestion/thresholds.py` match the report's recommendation.
