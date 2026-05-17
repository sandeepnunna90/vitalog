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

---

## Implementation Plan

### Key finding: numpy is not in dependencies

`pyproject.toml` lists `reportlab>=4.0.0` (ready to use, mypy-suppressed in `mypy.ini`) but **not numpy**. Use `random.Random(seed)` from stdlib — it is deterministic, seeded, and sufficient for uniform sampling over float ranges. No new dependency needed.

### PDF byte-reproducibility strategy

Reportlab embeds a creation timestamp in PDF metadata by default, which breaks byte-identity. Fix: pass a fixed `datetime` (epoch = `datetime(1970, 1, 1)`) as the document creation date. This makes metadata deterministic when the seed is fixed.

### H1 compatibility

The core `generate_report()` function accepts keyword overrides so H1 can drive specific `collection_date`, `lab_source`, and individual biomarker values for the hero dataset (9 HbA1c points across 3 labs).

---

### Files to create

#### `src/eval/__init__.py`
Empty package marker.

#### `src/eval/synthesis/__init__.py`
Exports `generate_report` for programmatic use by H1.
```python
from src.eval.synthesis.vendor_templates.quest import generate_report as generate_report
__all__ = ["generate_report"]
```

#### `src/eval/synthesis/vendor_templates/__init__.py`
Empty package marker.

#### `src/eval/synthesis/content_generator.py`

```python
from __future__ import annotations
import random
from dataclasses import dataclass

# Plausible clinical range (low, high, decimals, display_unit) per vitalog_id
BIOMARKER_RANGES: dict[str, tuple[float, float, int, str]] = {
    "hba1c":           (4.0,   12.0,  1, "%"),
    "fasting_glucose": (70.0,  300.0, 0, "mg/dL"),
    "total_cholesterol":(120.0, 320.0, 0, "mg/dL"),
    "ldl_cholesterol": (50.0,  250.0, 0, "mg/dL"),
    "hdl_cholesterol": (25.0,  90.0,  0, "mg/dL"),
    "triglycerides":   (50.0,  500.0, 0, "mg/dL"),
    "egfr":            (15.0,  120.0, 0, "mL/min/1.73m2"),
    "creatinine":      (0.5,   3.0,   2, "mg/dL"),
    "tsh":             (0.1,   10.0,  2, "mIU/L"),
    "vitamin_d":       (10.0,  80.0,  1, "ng/mL"),
    "hemoglobin":      (10.0,  18.0,  1, "g/dL"),
    "wbc":             (3.0,   14.0,  1, "10*3/uL"),
    "platelets":       (100.0, 500.0, 0, "10*3/uL"),
    "sodium":          (130.0, 150.0, 0, "mEq/L"),
    "potassium":       (3.0,   6.0,   1, "mEq/L"),
    "bun":             (5.0,   40.0,  0, "mg/dL"),
}

# Reference ranges displayed in the PDF (what the lab prints, not guideline ranges)
LAB_REFERENCE_RANGES: dict[str, str] = {
    "hba1c":            "4.0-5.6%",
    "fasting_glucose":  "70-99 mg/dL",
    "total_cholesterol":"<200 mg/dL",
    "ldl_cholesterol":  "<100 mg/dL",
    "hdl_cholesterol":  ">40 mg/dL",
    "triglycerides":    "<150 mg/dL",
    "egfr":             ">=60 mL/min/1.73m2",
    "creatinine":       "0.74-1.35 mg/dL",
    "tsh":              "0.5-4.5 mIU/L",
    "vitamin_d":        "30-100 ng/mL",
    "hemoglobin":       "13.5-17.5 g/dL",
    "wbc":              "4.5-11.0 10*3/uL",
    "platelets":        "150-400 10*3/uL",
    "sodium":           "136-145 mEq/L",
    "potassium":        "3.5-5.0 mEq/L",
    "bun":              "7-20 mg/dL",
}

# Display name as it appears in the Quest-style PDF
DISPLAY_NAMES: dict[str, str] = {
    "hba1c":            "HbA1c",
    "fasting_glucose":  "Glucose, Fasting",
    "total_cholesterol":"Cholesterol, Total",
    "ldl_cholesterol":  "LDL Cholesterol",
    "hdl_cholesterol":  "HDL Cholesterol",
    "triglycerides":    "Triglycerides",
    "egfr":             "eGFR",
    "creatinine":       "Creatinine",
    "tsh":              "TSH",
    "vitamin_d":        "Vitamin D, 25-OH",
    "hemoglobin":       "Hemoglobin",
    "wbc":              "WBC",
    "platelets":        "Platelets",
    "sodium":           "Sodium",
    "potassium":        "Potassium",
    "bun":              "BUN",
}

@dataclass
class BiomarkerReading:
    vitalog_id: str
    original_name: str      # as printed in PDF
    original_value: str     # string, e.g. "6.1"
    original_unit: str
    original_range: str
    flag: str               # "H", "L", or ""

def generate_readings(seed: int) -> list[BiomarkerReading]:
    rng = random.Random(seed)
    readings: list[BiomarkerReading] = []
    for vid, (lo, hi, decimals, unit) in BIOMARKER_RANGES.items():
        raw = rng.uniform(lo, hi)
        value = round(raw, decimals)
        value_str = f"{value:.{decimals}f}"
        readings.append(BiomarkerReading(
            vitalog_id=vid,
            original_name=DISPLAY_NAMES[vid],
            original_value=value_str,
            original_unit=unit,
            original_range=LAB_REFERENCE_RANGES[vid],
            flag="",   # flag logic out of scope for capstone
        ))
    return readings
```

#### `src/eval/synthesis/ground_truth_writer.py`

```python
from __future__ import annotations
import json
from pathlib import Path
from src.eval.synthesis.content_generator import BiomarkerReading

def write_ground_truth(
    path: Path,
    readings: list[BiomarkerReading],
    collection_date: str,
    lab_source: str,
) -> None:
    payload = {
        "document_type": "lab_report",
        "lab_source": lab_source,
        "collection_date": collection_date,
        "patient_name": "TEST PATIENT",
        "patient_dob": "1970-01-01",
        "biomarkers": [
            {
                "vitalog_id": r.vitalog_id,
                "original_name": r.original_name,
                "original_value": r.original_value,
                "original_unit": r.original_unit,
                "original_range": r.original_range,
                "collection_date": collection_date,
                "lab_source": lab_source,
            }
            for r in readings
        ],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
```

#### `src/eval/synthesis/vendor_templates/quest.py`

Core function: `generate_report(seed, out_dir, *, collection_date=None, lab_source=None) -> tuple[Path, Path]`

Layout using reportlab `SimpleDocTemplate` with `Table`:
- **Header**: "Quest Diagnostics" bold, address line, accession # (SYNTHETIC-{seed:06d})
- **Patient block**: Name: TEST PATIENT | DOB: 1970-01-01 | MRN: TEST-{seed:04d}
- **Results table**: columns = [Test Name, Result, Units, Reference Range, Flag]
- **Footer**: "Collection Date: {date} | Report Date: 1970-01-01 | SYNTHETIC — VITALOG EVAL"

Reproducibility: set `doc.build()` with patched `canvas._doc.info.producer` and fixed `creationDate`:
```python
from datetime import datetime
EPOCH = datetime(1970, 1, 1, 0, 0, 0)
# Pass to SimpleDocTemplate: no standard kwarg, but we patch after build:
# canvas.setAuthor("Vitalog Eval"); canvas.setCreator("Vitalog"); 
# canvas._doc.info.dateStamp = EPOCH  # internal reportlab field
```
Alternatively: use `canvas.setCreationDate(EPOCH)` if available in reportlab 4.x, else subclass `BaseDocTemplate` and override `_doSave`.

The simplest approach: build the PDF content into a `BytesIO`, which avoids any filesystem timestamp embedding. Then write the bytes to disk deterministically.

```python
def generate_report(
    seed: int,
    out_dir: Path,
    *,
    collection_date: str | None = None,
    lab_source: str = "Quest Diagnostics",
) -> tuple[Path, Path]:
    ...
```

#### `scripts/generate_synthetic.py`

```python
#!/usr/bin/env python3
"""CLI: python scripts/generate_synthetic.py --vendor quest --count 5 --seed 42 --out eval_corpus/synthetic/"""
import argparse, sys
from pathlib import Path
from src.eval.synthesis.vendor_templates.quest import generate_report

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vendor", required=True, choices=["quest"])
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    for i in range(args.count):
        doc_seed = args.seed + i
        pdf, gt = generate_report(doc_seed, args.out)
        print(f"  {pdf.name}  +  {gt.name}")

if __name__ == "__main__":
    main()
```

---

### Tests

#### `tests/eval/test_synthesis_reproducibility.py`
- Call `generate_report(seed=42, out_dir=tmp_path)` twice (different `tmp_path`)
- Assert PDF bytes are identical
- Assert ground truth JSON bytes are identical

#### `tests/eval/test_ground_truth_invariants.py`
- Call `generate_report(seed=1, out_dir=tmp_path)`
- Parse ground truth JSON
- Assert top-level keys: `document_type`, `lab_source`, `collection_date`, `patient_name`, `patient_dob`, `biomarkers`
- For each biomarker entry: assert keys `vitalog_id`, `original_name`, `original_value`, `original_unit`, `original_range`, `collection_date`, `lab_source`
- Assert `patient_name == "TEST PATIENT"`, `patient_dob == "1970-01-01"`
- Assert `len(biomarkers) == len(BIOMARKER_RANGES)` (all 16 biomarkers present)

---

### Mypy notes

- `reportlab.*` already has `ignore_missing_imports = True` in `mypy.ini`
- No numpy — stdlib `random` is fully typed
- All functions need explicit return types; dataclass fields need annotations

---

### Verification

```bash
pytest tests/eval/ -q
python scripts/generate_synthetic.py --vendor quest --count 3 --seed 1 --out /tmp/s1
python scripts/generate_synthetic.py --vendor quest --count 3 --seed 1 --out /tmp/s2
diff -r /tmp/s1 /tmp/s2   # must be empty
make lint && make typecheck
```
