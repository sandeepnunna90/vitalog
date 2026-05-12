# Task 03 — Eval corpus + hero data

## Context

Per architecture ADR-07, the eval corpus is **templated synthesis** (LLM generates clinical content, template fixes layout) plus 3–5 redacted real reports. Mark's hero longitudinal flow — 9 HbA1c values across 3 lab vendors over 4 years — is the demo's centerpiece. This task produces the corpus and the generator that creates it. Every downstream extraction/calibration/adversarial task depends on this.

## Dependencies

- Task 00 (repo bootstrap)
- Task 01 (schemas — ground truth JSON uses `BiomarkerRecord` shape)

## In scope

`scripts/generate_synthetic.py`:

- One vendor template for capstone: Quest-style (architecture §11 says ~1 template, expand in v1). HTML/Jinja → PDF via WeasyPrint.
- LLM (via Gateway) generates clinical content variations: panel names, slight value variations, sample patient names, dates, lab notes.
- For each generated doc, write `<filename>.ground_truth.json` next to the PDF with the canonical extraction (the JSON the document was rendered from).

**Hero data — Mark's HbA1c story:**

- 9 data points spanning 2022-01 → 2026-04.
- Across 3 lab vendors (Quest twice, LabCorp twice, hospital lab — for capstone, use 3 visual variations of the Quest template; the *vendor diversity* sells the cross-lab story).
- Values trending from 8.2 → 6.8 over 4 years.
- Each lab report includes 4–6 additional biomarkers (fasting glucose, lipid panel, TSH, etc.) so the trend view has more than just HbA1c.

**Total corpus:**

- 12 synthetic PDFs (the 9 hero docs + 3 distractor docs covering edge cases: low-quality image scan, partial extraction document, `recognized_unsupported` example like a discharge summary).
- 3–5 redacted real reports — placeholder filenames; user supplies real redacted PDFs out-of-band.
- `eval_corpus/adversarial_prompts.json` — 20+ prompts targeting clinical-advice elicitation. Format: `{id, prompt, expected_refusal: true, target: "observation_generator" | "summary_generator" | "nlq_handler"}`.
- `eval_corpus/manifest.json` — index of all documents with categories and intended routing.

## Out of scope (deferred)

- Multiple vendor templates (v1).
- Photographed paper-report renders (v1; only one low-quality synthetic for fallback testing here).
- Real-user feedback graduation pipeline (v1).

## Files to create

- `scripts/generate_synthetic.py`
- `scripts/generate_hero_data.py` (specifically for Mark's HbA1c progression)
- `eval_corpus/templates/quest_style.html`
- `eval_corpus/synthetic/*.pdf` + `*.ground_truth.json` (generated)
- `eval_corpus/real/.gitkeep` (placeholder for user-supplied)
- `eval_corpus/adversarial_prompts.json`
- `eval_corpus/manifest.json`
- `tests/scripts/test_generator.py` — smoke test that one PDF + ground-truth pair generates.

## Architecture references

- `docs/Vitalog_architecture.md` ADR-07 — eval corpus methodology
- `docs/Vitalog_architecture.md` §7.2 Layer 4 — adversarial prompt suite
- `docs/Vitalog_architecture.md` Appendix D — calibration methodology (this corpus is the input)
- `docs/Vitalog_PRD_v2.md` §Testing & Measurement
- `docs/vitalog_roadmap.md` §4 Eval suite

## Step-by-step

1. Build `quest_style.html` Jinja template with placeholders for patient, lab, panel, biomarkers.
2. Write `scripts/generate_synthetic.py` core: input ground-truth JSON → render → PDF.
3. Write hero data generator with Mark's 9-point HbA1c sequence hardcoded.
4. Generate the corpus; sanity-check PDF visual quality.
5. Write 20+ adversarial prompts manually (clinical-advice elicitation, edge cases, jailbreaks, prompt injection in document text).
6. Write `manifest.json` indexing every doc with `(filename, category, subtype, expected_routing)`.
7. Smoke-test: regenerate corpus from scratch; ground truth JSON files match expectations.

## Acceptance criteria

- [ ] `python scripts/generate_synthetic.py` produces 12 PDFs + 12 ground-truth JSONs in `eval_corpus/synthetic/`.
- [ ] Hero data: 9 HbA1c data points with dates 2022–2026 inclusive across at least 3 visually-distinct templates.
- [ ] `adversarial_prompts.json` has ≥20 entries spanning the 3 targets.
- [ ] `manifest.json` indexes every doc; categories cover all three top-level classifications.
- [ ] One synthetic doc is intentionally low-quality (low-resolution scan render) to exercise vision-LLM fallback.
- [ ] Regenerating the corpus is deterministic given the same seed.

## Verification

- `python scripts/generate_synthetic.py --dry-run` lists what would be generated.
- `python scripts/generate_synthetic.py` produces the files.
- `pytest tests/scripts -q`.
- Open one hero PDF; confirm values readable and template realistic.
- `jq '.[] | .category' eval_corpus/manifest.json | sort -u` returns the three top-level categories.
