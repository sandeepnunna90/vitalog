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

- `src/eval/synthesis/vendor_templates/quest.py` — **improve** existing template with correct labels, panel grouping, column widths
- `src/eval/synthesis/vendor_templates/labcorp.py` — **new** LabCorp template (based on user's real reports; placeholder until PDFs provided)
- `src/eval/synthesis/vendor_templates/hospital.py` — **new** hospital/Epic 4-column format
- `src/eval/synthesis/__init__.py` — export all 3 `generate_report` variants
- `scripts/generate_synthetic.py` — add `--vendor labcorp` and `--vendor hospital`
- `scripts/redact_real.py` — **new** PyMuPDF helper to redact HIPAA Safe Harbor identifiers from user-provided PDFs
- `scripts/build_manifest.py` — hashes every PDF + ground_truth.json, writes manifest
- `eval_corpus/synthetic/` — 10 PDFs + 10 ground_truth.json (generated)
- `eval_corpus/redacted_real/` — 3–5 LabCorp PDFs (user-provided, redacted) + ground_truth.json + redaction_notes.md
- `eval_corpus/adversarial/` — 3 PDFs + ground_truth.json + failure_mode_under_test.md
- `eval_corpus/manifest.json` — corpus manifest with hashes
- `eval_corpus/redaction_checklist.md` — the HIPAA Safe Harbor checklist followed during redaction
- `tests/eval/test_corpus_integrity.py` — fails if any file's hash diverges from the manifest

## Implementation notes

### Synthesizer improvements (expanded from original)

C1 built one developer-approximated Quest template. C2 improves it and adds two more based on real formats:

**Quest template fixes** (based on CLSI EP28-A3c and Quest patient education materials):
- Column 5 header: "Reference Interval" (not "Reference Range") — Quest standardized on this post-2018
- Patient block: "Specimen ID" (not "Accession #"), "Ordering Physician", "Patient ID"
- Date block: three rows — Collected / Received / Reported (MM/DD/YYYY HH:MM)
- Panel grouping: bold all-caps panel header rows; test rows indented
  - METABOLIC PANEL: fasting_glucose, egfr, creatinine, bun, sodium, potassium
  - LIPID PANEL: total_cholesterol, ldl_cholesterol, hdl_cholesterol, triglycerides
  - ADDITIONAL TESTS: hba1c, tsh, vitamin_d, hemoglobin, wbc, platelets
- Column widths (7.5in usable): TestName 3.0in / Result 0.9in / Flag 0.4in / Units 0.8in / RefInterval 1.4in

**Hospital/Epic template** (new — 4-column format):
- Columns: Test / Result / Reference Range / Units
- Flag embedded in Result cell ("7.2 H") — no separate flag column
- Header uses: "MRN", "Age", "Ordering Provider", "Accession"
- Panel headers: bold with light gray background band
- Lab name default: "Memorial Hospital Laboratory"

**LabCorp template** (new — deferred until user provides real PDFs):
- Placeholder `NotImplementedError` until layout is confirmed from real reports
- User provides personal LabCorp reports → `scripts/redact_real.py` redacts PII → layout inspected → template built

### Redacted real split

- User provides personal LabCorp PDFs (3–5 reports)
- `scripts/redact_real.py` uses PyMuPDF (`page.search_for()` + `page.add_redact_annot()` + `page.apply_redactions()`) to strip the 18 HIPAA Safe Harbor identifiers: name, DOB details, address, phone, MRN, accession number, ordering physician, NPI
- Ground truth JSON curated manually after redaction (exact field values as printed)
- `redaction_notes.md` documents what was removed from each doc
- `redaction_checklist.md` is the Safe Harbor checklist

### Synthetic 10

Distribution across vendors: 4 × Quest (seed 100–103), 3 × LabCorp (seed 200–202, deferred), 3 × hospital (seed 300–302).
Three value profiles: "all in range", "T2D-typical" (HbA1c 7.5, fasting_glucose 145, etc.), "mixed" (default random).
Note: H1's 9-point HbA1c hero dataset is separate — generated by `scripts/build_hero_data.py`, not counted here.

### Adversarial 3

- (a) **Photo-of-paper**: Quest PDF → PyMuPDF render to image (150 dpi) → PIL effects (±2° rotation, Gaussian blur r=0.8, glare overlay) → image-only PDF. Tests vision-LLM fallback when Textract can't extract structured text.
- (b) **Multi-page mixed**: Page 1 = Quest lab report (seed 999), Page 2 = discharge summary paragraphs. Tests classifier identifies `lab_report` from leading page.
- (c) **mmol/mol HbA1c**: Quest report with HbA1c unit overridden to `"mmol/mol"`, value `"48"`, range `"20-42 mmol/mol"`. Tests E3 unit conversion path.

### Manifest

SHA-256 hashes of every PDF + ground_truth.json. Stores split, vendor, expected_classification per document. Integrity test fails if any file is modified without re-running `build_manifest.py`.

### Sequencing

1. Improve Quest + add hospital template → synthetic (Quest + hospital) + adversarial docs
2. User provides LabCorp PDFs → redact → inspect layout → build LabCorp template → synthetic (LabCorp)
3. Finalize corpus → `build_manifest.py` → integrity test

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
