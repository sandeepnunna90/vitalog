# H1 — Hero longitudinal dataset (HbA1c × 9 × 3 labs)

**Epic:** Demo
**Points:** 3
**Priority:** Critical
**Depends on:** C1, A2
**Architecture refs:** roadmap §4 (hero data); PRD v2 Success Criteria + Demo Slice

## User story

As the founder preparing the demo,
I want 9 synthetic HbA1c results across 3 different lab vendors over 4 years, pre-generated and committed to the repo,
So that on demo day the trend chart is dramatic, complete, and uploadable end-to-end in under 5 minutes.

## Why this matters

PRD v2 Success Criteria #2: "Mark can view a longitudinal trend for HbA1c across 9 data points from 3 different labs — on one chart." Roadmap key risk #2 calls out "Hero longitudinal data not generated until too late" as a demo failure mode. Pre-generating this on Day 1 of the demo phase removes that risk.

## Acceptance criteria

1. **Given** the generation script, **When** I run `python scripts/build_hero_data.py`, **Then** 9 paired files are produced: `hero/hba1c_2022_q1_quest.pdf` + `.ground_truth.json`, …, `hero/hba1c_2026_q1_quest.pdf` + `.ground_truth.json`, covering 9 dates over 4 years.
2. **Given** the 9 docs, **When** I count vendors, **Then** at least 3 distinct lab sources are represented (e.g., Quest, LabCorp-style, hospital-style). For capstone with one vendor template (C1), the variation is in the rendered `lab_source` string + minor layout variants on the same template.
3. **Given** the dataset, **When** I plot the HbA1c values by date, **Then** they tell a coherent story consistent with Mark's T2D progression: e.g., 9.2% → 8.5% → 7.8% → 7.4% → 7.0% → 6.8% → 6.9% → 6.7% → 6.5% — initial diagnosis → metformin → stabilization → near target.
4. **Given** the dataset, **When** uploaded end-to-end via the MCP pipeline, **Then** all 9 records auto-accept (composite confidence ≥ THRESHOLD_AUTO_ACCEPT) and land in Mark's record under `canonical_id="hba1c"`.
5. **Given** the hero dataset, **When** `get_trend(mark, "hba1c")` runs, **Then** the response has exactly 9 points, sorted ascending by date, with the ADA T2D target band overlaid.
6. **Given** repo discipline, **When** I `ls eval_corpus/hero/`, **Then** the dataset is present and tracked in git so it's reproducible from any clone.

## Files to create / modify

- `scripts/build_hero_data.py` — deterministic generation calling C1's synthesizer with hardcoded seeds + dates + lab names
- `eval_corpus/hero/` — 9 PDFs + 9 ground_truth.json files (committed)
- `eval_corpus/hero/manifest.json` — hashes + expected trend story
- `tests/eval/test_hero_dataset.py` — invariants: count, distinct vendors, ground-truth value progression matches the story

## Implementation notes

- Dates: 2022-03-15, 2022-09-20, 2023-03-10, 2023-09-15, 2024-03-12, 2024-09-18, 2025-03-14, 2025-09-22, 2026-03-12. (Adjust slightly to land on plausible business days.)
- Lab sources: rotate among `"Quest Diagnostics"`, `"LabCorp"`, `"Memorial Hospital Lab"` — the C1 template stays Quest-style but the rendered `lab_source` header text varies.
- Values: deterministic via seeded sampling around the target story curve, with realistic noise (±0.1%).
- The 9 docs join the eval corpus but are also tagged as `hero` in the manifest so accuracy reports can call them out specifically.
- The build script is idempotent — running it twice produces identical bytes (reproducibility per C1's seeding).

## Verification

- `python scripts/build_hero_data.py && pytest tests/eval/test_hero_dataset.py -q`
- Manual: open 2–3 of the PDFs, confirm they look like distinct lab reports
- End-to-end demo prep: ingest all 9 sequentially via the MCP upload tool, confirm trend chart renders 9 points with ADA T2D band

## INVEST check

- [x] Independent — C1 + A2 required
- [x] Negotiable — exact values flexible within the story arc
- [x] Valuable — the demo's headline moment
- [x] Estimable — well-bounded scripting
- [x] Small — 3 pts
- [x] Testable — invariants + end-to-end

## Deferred (explicitly out of this story)

- Multiple-biomarker hero datasets (BP, lipids) — would be useful but capstone only commits to HbA1c
- Hero dataset for endocrinology — v1 once endocrinology specialist lands

## Notes / changelog

_(append after work is done)_
