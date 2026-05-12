# C2 — Eval corpus assembly (~18 docs)

**Epic:** Eval Corpus & Harness
**Points:** 3
**Priority:** High
**Depends on:** C1
**Architecture refs:** ADR-07; PRD v2 Testing & Measurement; architecture §11

## User story

As the founder building Vitalog,
I want an assembled eval corpus of ~18 documents (10 synthetic + 3–5 redacted real + 3 adversarial) with paired ground truth,
So that extraction accuracy, classification accuracy, and confidence calibration can all be measured against the same fixed set.

## Why this matters

The corpus is the substrate for every quantitative claim Vitalog makes about itself — accuracy, calibration boundaries, classification precision. If it's ad-hoc, none of those claims hold. Assembling and freezing the corpus before C3 / C5 run means measurements are repeatable.

## Acceptance criteria

1. **Given** the corpus directory, **When** I `ls eval_corpus/`, **Then** I see exactly three subdirectories: `synthetic/`, `redacted_real/`, `adversarial/`.
2. **Given** the synthetic split, **When** I count files, **Then** there are 10 PDFs and 10 paired `ground_truth.json` files.
3. **Given** the redacted real split, **When** I count files, **Then** there are 3–5 redacted real PDFs each paired with a manually-curated `ground_truth.json` and a `redaction_notes.md` documenting what was removed.
4. **Given** the adversarial split, **When** I count files, **Then** there are 3 PDFs designed to be intentionally hard (e.g., poor photo, multi-page mix, unusual unit) each with `ground_truth.json` and a `failure_mode_under_test.md`.
5. **Given** the corpus manifest, **When** I read `eval_corpus/manifest.json`, **Then** every document is listed with its split, vendor, expected classification, and hash for tamper detection.
6. **Given** the redaction process, **When** I open any redacted real PDF, **Then** zero of the 18 HIPAA Safe Harbor identifiers are present (verified by a redaction-checklist review).

## Files to create / modify

- `eval_corpus/synthetic/` — populated by running C1
- `eval_corpus/redacted_real/` — manually populated (this is the manual labor of the story)
- `eval_corpus/adversarial/` — manually populated
- `eval_corpus/manifest.json` — corpus manifest with hashes
- `eval_corpus/redaction_checklist.md` — the checklist the founder followed
- `scripts/build_manifest.py` — hashes every PDF + ground_truth.json, writes manifest
- `tests/eval/test_corpus_integrity.py` — fails if any file's hash diverges from the manifest

## Implementation notes

- Synthetic 10: 7 Quest-style + 3 variations using same template with different value distributions (one "all in range", one "T2D-typical", one "mixed normal/abnormal"). Include the 9-point HbA1c history Mark needs — those nine docs count toward the 10 (one extra is a non-HbA1c control).
- Redacted real 3–5: founder sources from personal records, redacts manually per Safe Harbor checklist. Capstone explicitly does NOT have a full Safe Harbor pipeline; this is a one-time manual redaction step.
- Adversarial 3: (a) photograph-of-paper with mild glare; (b) multi-page PDF where second page is a discharge summary (tests classification on the leading page); (c) report using `mmol/mol` for HbA1c instead of `%` (tests unit conversion).
- Manifest hashes are SHA-256. Tampering with any corpus file fails the integrity test.
- The manifest also stores expected classification (`lab_report` / `recognized_unsupported` / `not_supported`) for the adversarial mixed-content doc — used by classification accuracy eval.

## Verification

- `python scripts/build_manifest.py && pytest tests/eval/test_corpus_integrity.py -q`
- Manual: redaction checklist signed off (one final pass against all 3–5 real docs)
- `wc -l eval_corpus/redacted_real/*.ground_truth.json` — sanity-check that ground truth is non-trivial

## INVEST check

- [x] Independent — only C1 required (synthesizer)
- [x] Negotiable — exact mix of synthetic / real / adversarial is fixed by ADR-07
- [x] Valuable — gates every measurement
- [x] Estimable — bounded manual + scripted work
- [x] Small — 3 pts (synthetic auto, real/adversarial manual)
- [x] Testable — integrity test enforces corpus stability

## Deferred (explicitly out of this story)

- Expanded corpus to ~75 docs (v1)
- Real-user feedback loop graduating new docs into the corpus (v1)
- Per-vendor accuracy breakouts beyond Quest (v1 once LabCorp / hospital templates exist)

## Notes / changelog

_(append after work is done)_
