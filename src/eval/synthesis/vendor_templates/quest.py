"""Quest Diagnostics-style synthetic PDF renderer."""

from __future__ import annotations

import io
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from src.eval.synthesis.content_generator import BiomarkerReading, generate_readings
from src.eval.synthesis.ground_truth_writer import write_ground_truth

_CREATION_DATE_RE = re.compile(rb"/CreationDate\s*\(D:[^)]+\)")
_MOD_DATE_RE = re.compile(rb"/ModDate\s*\(D:[^)]+\)")
_PRODUCER_RE = re.compile(rb"/Producer\s*\([^)]*\)")
_CREATOR_RE = re.compile(rb"/Creator\s*\([^)]*\)")
# /ID [<hex1><hex2>] — trailer document ID hash varies per build
_ID_RE = re.compile(rb"/ID\s*\[<[0-9a-fA-F]+><[0-9a-fA-F]+>\]")
_FIXED_ID = b"/ID [<00000000000000000000000000000000><00000000000000000000000000000000>]"


def _make_reproducible(pdf_bytes: bytes) -> bytes:
    """Replace all timestamp/hash fields so output is byte-identical for same seed."""
    epoch = b"D:19700101000000+00'00'"
    pdf_bytes = _CREATION_DATE_RE.sub(b"/CreationDate (" + epoch + b")", pdf_bytes)
    pdf_bytes = _MOD_DATE_RE.sub(b"/ModDate (" + epoch + b")", pdf_bytes)
    pdf_bytes = _PRODUCER_RE.sub(b"/Producer (Vitalog Eval)", pdf_bytes)
    pdf_bytes = _CREATOR_RE.sub(b"/Creator (Vitalog Eval)", pdf_bytes)
    pdf_bytes = _ID_RE.sub(_FIXED_ID, pdf_bytes)
    return pdf_bytes


def _build_pdf(
    readings: list[BiomarkerReading],
    seed: int,
    collection_date: str,
    lab_source: str,
) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=LETTER,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )
    styles = getSampleStyleSheet()
    normal = styles["Normal"]
    bold = styles["h2"]

    elements = []

    # Header
    elements.append(Paragraph(lab_source, bold))
    elements.append(Paragraph("123 Lab Blvd, Anytown, CA 90000 | (800) 555-0000", normal))
    elements.append(Paragraph(f"Accession #: SYNTHETIC-{seed:06d}", normal))
    elements.append(Spacer(1, 0.15 * inch))

    # Patient block
    elements.append(
        Paragraph(
            f"Patient: TEST PATIENT | DOB: 1970-01-01 | MRN: TEST-{seed:04d}",
            normal,
        )
    )
    elements.append(Spacer(1, 0.2 * inch))

    # Results table
    table_data = [["Test Name", "Result", "Units", "Reference Range", "Flag"]]
    for r in readings:
        table_data.append(
            [r.original_name, r.original_value, r.original_unit, r.original_range, r.flag]
        )

    col_widths = [2.2 * inch, 0.8 * inch, 1.1 * inch, 1.8 * inch, 0.5 * inch]
    tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.Color(0.95, 0.95, 0.95)],
                ),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    elements.append(tbl)
    elements.append(Spacer(1, 0.2 * inch))

    # Footer
    elements.append(
        Paragraph(
            f"Collection Date: {collection_date} | Report Date: 1970-01-01 | "
            "SYNTHETIC — VITALOG EVAL",
            normal,
        )
    )

    doc.build(elements)
    raw = buf.getvalue()
    return _make_reproducible(raw)


def generate_report(
    seed: int,
    out_dir: Path,
    *,
    collection_date: str | None = None,
    lab_source: str = "Quest Diagnostics",
    overrides: dict[str, str] | None = None,
) -> tuple[Path, Path]:
    """Render one synthetic Quest-style PDF + ground-truth JSON pair.

    Returns (pdf_path, ground_truth_path).
    overrides maps vitalog_id → value string for H1 hero dataset pins.
    out_dir must exist before calling; created with mkdir if needed.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    date = collection_date or "1970-01-01"
    pdf_path = out_dir / f"synthetic_{seed:06d}.pdf"
    gt_path = out_dir / f"synthetic_{seed:06d}.ground_truth.json"

    readings = generate_readings(seed, overrides)
    pdf_bytes = _build_pdf(readings, seed, date, lab_source)
    pdf_path.write_bytes(pdf_bytes)
    write_ground_truth(gt_path, readings, date, lab_source)

    return pdf_path, gt_path
