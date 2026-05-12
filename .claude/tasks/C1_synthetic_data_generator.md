# C1 — Synthetic data generator

**Epic:** Eval Corpus & Harness
**Points:** 5
**Priority:** High
**Depends on:** A2
**Architecture refs:** ADR-07; PRD v2 Testing & Measurement

## User story

As the founder building Vitalog,
I want a script that generates synthetic lab report PDFs where the underlying JSON is itself the ground truth,
So that I can grow the eval corpus without manually transcribing 10+ documents, and accuracy measurement is exact rather than approximate.

## Why this matters

ADR-07 is "templated synthesis + 3–5 redacted real". Templated synthesis is the only way a solo founder gets a corpus large enough to calibrate confidence thresholds in week 2. Because the JSON renders the PDF, ground truth doesn't drift — extraction accuracy is "does the parser recover the JSON?" with zero subjective grading.

## Acceptance criteria

1. **Given** a CLI invocation `python scripts/generate_synthetic.py --vendor quest --count 5 --out eval_corpus/synthetic/`, **When** it completes, **Then** 5 paired files exist: 5 PDFs + 5 `*.ground_truth.json` files.
2. **Given** a Quest-style vendor template, **When** I render a synthetic report, **Then** the layout includes a header (lab name, address, accession #), a patient block (synthetic name, DOB), a results table (biomarker | value | unit | reference range | flag), and a footer with collection/report dates.
3. **Given** the ground-truth JSON, **When** I parse it, **Then** every biomarker entry has `vitalog_id`, `original_name` (as it appears in the PDF), `original_value`, `original_unit`, `original_range`, `collection_date`, `lab_source`.
4. **Given** the synthesizer, **When** I run it twice with the same `--seed 42`, **Then** the outputs are byte-identical (reproducible synthesis).
5. **Given** synthetic data, **When** I inspect any record, **Then** all PII fields use a clearly fake pattern (e.g., name "TEST PATIENT", DOB `1970-01-01`, MRN `TEST-XXXX`) so the file is unambiguously synthetic.
6. **Given** the LLM-content path, **When** the script generates biomarker values, **Then** they are drawn from physiologically-plausible distributions per biomarker (e.g., HbA1c ∈ [4.0, 12.0]%) — not LLM-hallucinated free-form numbers.

## Files to create / modify

- `scripts/generate_synthetic.py` — CLI entry point
- `src/eval/synthesis/__init__.py`
- `src/eval/synthesis/vendor_templates/quest.py` — Quest-style PDF renderer using `reportlab`
- `src/eval/synthesis/content_generator.py` — physiologically-plausible value sampler (deterministic from seed)
- `src/eval/synthesis/ground_truth_writer.py`
- `tests/eval/test_synthesis_reproducibility.py`
- `tests/eval/test_ground_truth_invariants.py`

## Implementation notes

- One vendor template ships in capstone (Quest-style). Architecture §11 commits to 1; v1 adds LabCorp + hospital.
- The content generator is a `numpy.random.default_rng(seed)` consumer per biomarker. No LLM call required for value generation — the *layout* is templated, the *content* is deterministic sampling.
- Use `reportlab` for PDF rendering (already in `pyproject.toml` per A1). Fonts must be embeddable so Textract sees consistent glyphs.
- The PDF must be text-extractable (selectable text), not just rasterized — the structurer's primary path depends on Textract giving back text + tables.
- For Mark's hero data (9-point HbA1c), the generator is invoked by H1 with specific seeds + dates + lab names; design the function signature so H1 can deterministically reproduce the hero set.
- Synthetic flag: every generated PDF must include a tiny watermark "SYNTHETIC — VITALOG EVAL" in the footer so it can never be confused with real data.

## Verification

- `pytest tests/eval/ -q`
- Run `python scripts/generate_synthetic.py --vendor quest --count 3 --seed 1 --out /tmp/s1 && python scripts/generate_synthetic.py --vendor quest --count 3 --seed 1 --out /tmp/s2 && diff -r /tmp/s1 /tmp/s2` — output must be identical
- Manual: open a generated PDF, confirm Textract-readable text + the synthetic watermark

## INVEST check

- [x] Independent — only A2 required
- [x] Negotiable — exact template style flexible
- [x] Valuable — gates C2, C3, C5, H1
- [x] Estimable — well-bounded scripting
- [x] Small — 5 pts
- [x] Testable — reproducibility + ground-truth invariants

## Deferred (explicitly out of this story)

- LabCorp + hospital vendor templates (v1)
- Adversarial document synthesis with intentional flaws (covered by C4 prompt suite, not document synthesis)
- Image / photo-of-paper synthesis (the corpus uses real photos via the redacted-real path)

## Notes / changelog

_(append after work is done)_
