#!/usr/bin/env python3
"""Generate the 3 adversarial corpus documents for eval_corpus/adversarial/.

Adversarial docs test specific failure modes in the ingestion pipeline:
  001 — photo-of-paper simulation (image-only PDF, forces Textract OCR path)
  002 — multi-page mixed document (lab report + discharge summary, tests classifier)
  003 — mmol/mol HbA1c unit (tests E3 unit conversion path)

Run:
    python scripts/build_adversarial.py --out eval_corpus/adversarial/
"""

from __future__ import annotations

import argparse
import io
import json
from dataclasses import replace
from pathlib import Path

import fitz  # PyMuPDF
from PIL import Image, ImageEnhance, ImageFilter
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from src.eval.synthesis.content_generator import generate_readings
from src.eval.synthesis.ground_truth_writer import write_ground_truth
from src.eval.synthesis.vendor_templates.quest import _build_pdf, generate_report


def _build_001_photo_sim(out_dir: Path) -> None:
    """adversarial_001: image-only PDF simulating a photo of a printed lab report."""
    # Generate a clean Quest PDF to use as source
    tmp_dir = out_dir / "_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    pdf_path, _ = generate_report(seed=1, out_dir=tmp_dir, collection_date="2024-06-15")

    # Render to image at 150 DPI
    doc = fitz.open(str(pdf_path))
    page = doc[0]
    mat = fitz.Matrix(150 / 72, 150 / 72)
    pix = page.get_pixmap(matrix=mat)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    doc.close()

    # Apply photo-of-paper effects
    img = img.rotate(-1.5, expand=True, fillcolor=(255, 255, 255))  # type: ignore[arg-type]
    img = img.filter(ImageFilter.GaussianBlur(radius=0.8))
    img = ImageEnhance.Brightness(img).enhance(0.93)

    # Save as image-only PDF (no selectable text — forces Textract OCR path)
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="JPEG", quality=85)
    img_bytes.seek(0)

    out_doc = fitz.open()
    out_page = out_doc.new_page(width=612, height=792)
    out_page.insert_image(out_page.rect, stream=img_bytes.getvalue())
    out_path = out_dir / "adversarial_001_photo_sim.pdf"
    out_doc.save(str(out_path))
    out_doc.close()

    # Ground truth — same as the Quest seed=1 report
    gt = {
        "document_type": "lab_report",
        "lab_source": "Quest Diagnostics",
        "collection_date": "2024-06-15",
        "note": "Image-only PDF; ground truth derived from source Quest report seed=1",
    }
    (out_dir / "adversarial_001_photo_sim.ground_truth.json").write_text(json.dumps(gt, indent=2))
    (out_dir / "adversarial_001_photo_sim.failure_mode_under_test.md").write_text(
        "# Failure mode: photo-of-paper\n\n"
        "This PDF is image-only (no selectable text layer). Textract's primary table-extraction "
        "path will fail; the pipeline must fall back to the vision-LLM path.\n\n"
        "**Expected behaviour:** classified as `lab_report`; extraction via vision-LLM fallback.\n"
    )

    # Clean up tmp
    for f in tmp_dir.iterdir():
        f.unlink()
    tmp_dir.rmdir()
    print(f"  adversarial_001_photo_sim.pdf  (image-only, {out_path.stat().st_size} bytes)")


def _build_002_multipage(out_dir: Path) -> None:
    """adversarial_002: multi-page PDF — lab report on page 1, discharge summary on page 2."""
    # Page 1: Quest lab report (seed 999)
    tmp_dir = out_dir / "_tmp2"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    lab_path, gt_path = generate_report(seed=999, out_dir=tmp_dir, collection_date="2024-09-10")

    # Page 2: Discharge summary (plain text via reportlab)
    styles = getSampleStyleSheet()
    normal = styles["Normal"]
    discharge_buf = io.BytesIO()
    discharge_doc = SimpleDocTemplate(
        discharge_buf,
        pagesize=LETTER,
        leftMargin=inch,
        rightMargin=inch,
        topMargin=inch,
        bottomMargin=inch,
    )
    discharge_doc.build(
        [
            Paragraph("<b>DISCHARGE SUMMARY</b>", styles["h1"]),
            Spacer(1, 0.2 * inch),
            Paragraph("Patient: TEST PATIENT   DOB: 01/01/1970   MRN: TEST-9999", normal),
            Paragraph("Admission: 09/08/2024   Discharge: 09/10/2024", normal),
            Spacer(1, 0.15 * inch),
            Paragraph("<b>Principal Diagnosis:</b> Routine annual evaluation.", normal),
            Spacer(1, 0.1 * inch),
            Paragraph(
                "<b>Hospital Course:</b> Patient was admitted for elective monitoring. "
                "Labs were drawn on admission. Patient remained hemodynamically stable throughout. "
                "Discharged in good condition with follow-up in 4 weeks.",
                normal,
            ),
            Spacer(1, 0.1 * inch),
            Paragraph(
                "<b>Discharge Medications:</b> Metformin 1000mg BID, Lisinopril 10mg daily.",
                normal,
            ),
            Spacer(1, 0.1 * inch),
            Paragraph(
                "Electronically signed: J. Doe, MD   09/10/2024   SYNTHETIC — VITALOG EVAL",
                normal,
            ),
        ]
    )

    # Combine: lab report (page 1) + discharge summary (page 2) via PyMuPDF
    combined = fitz.open()
    lab_doc = fitz.open(str(lab_path))
    discharge_fitz = fitz.open("pdf", discharge_buf.getvalue())
    combined.insert_pdf(lab_doc)
    combined.insert_pdf(discharge_fitz)

    out_path = out_dir / "adversarial_002_multipage.pdf"
    page_count = combined.page_count
    combined.save(str(out_path))
    combined.close()
    lab_doc.close()
    discharge_fitz.close()

    # Ground truth — from the Quest seed=999 report
    import shutil

    shutil.copy(gt_path, out_dir / "adversarial_002_multipage.ground_truth.json")

    (out_dir / "adversarial_002_multipage.failure_mode_under_test.md").write_text(
        "# Failure mode: multi-page mixed document\n\n"
        "Page 1 is a Quest-style lab report. "
        "Page 2 is a discharge summary (not_supported content).\n\n"
        "**Expected behaviour:** classifier identifies `lab_report` from the leading page. "
        "The second page is ignored for extraction purposes.\n"
    )

    for f in tmp_dir.iterdir():
        f.unlink()
    tmp_dir.rmdir()
    print(f"  adversarial_002_multipage.pdf  ({page_count} pages)")


def _build_003_mmol_hba1c(out_dir: Path) -> None:
    """adversarial_003: Quest report with HbA1c in mmol/mol instead of %."""
    seed = 3
    date = "2024-01-15"

    # Generate all readings then override HbA1c unit/value/range
    readings = generate_readings(seed)
    readings = [
        replace(
            r,
            original_value="48",
            original_unit="mmol/mol",
            original_range="20-42 mmol/mol",
            flag="H",
        )
        if r.vitalog_id == "hba1c"
        else r
        for r in readings
    ]

    pdf_bytes = _build_pdf(readings, seed, date, "Quest Diagnostics")
    out_path = out_dir / "adversarial_003_mmol_hba1c.pdf"
    out_path.write_bytes(pdf_bytes)

    gt_path = out_dir / "adversarial_003_mmol_hba1c.ground_truth.json"
    write_ground_truth(gt_path, readings, date, "Quest Diagnostics")

    (out_dir / "adversarial_003_mmol_hba1c.failure_mode_under_test.md").write_text(
        "# Failure mode: non-standard HbA1c unit (mmol/mol)\n\n"
        "HbA1c is reported as 48 mmol/mol (flag H) instead of the common % unit.\n\n"
        "**Expected behaviour:** E3 unit conversion path converts 48 mmol/mol → ~6.5% "
        "before storing in `biomarker_records`. The stored `canonical_value` should be in %.\n"
    )
    print("  adversarial_003_mmol_hba1c.pdf  (HbA1c = 48 mmol/mol, flag H)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate adversarial eval corpus documents.")
    parser.add_argument("--out", type=Path, required=True, help="Output directory")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    print("Building adversarial corpus...")
    _build_001_photo_sim(args.out)
    _build_002_multipage(args.out)
    _build_003_mmol_hba1c(args.out)
    print(f"Done. Files written to: {args.out}")


if __name__ == "__main__":
    main()
