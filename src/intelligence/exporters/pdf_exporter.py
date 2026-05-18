"""PDF export for F6 — uses reportlab Platypus flowables."""

from __future__ import annotations

import io
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from src.intelligence.annotator import _parse_annotations
from src.persistence.models import SummaryRow

_SECTION_LABELS = {
    "conditions_section": "Active Conditions",
    "medications_section": "Current Medications",
    "results_section": "Biomarker Results",
    "trends_section": "Trends",
    "data_gaps_section": "Data Gaps",
    "patient_notes": "Patient Notes",
}

_SECTION_ORDER = list(_SECTION_LABELS.keys())


def export_pdf(row: SummaryRow) -> bytes:
    """Render a SummaryRow to PDF bytes using reportlab Platypus."""
    buf = io.BytesIO()
    disclaimer = row.content_json.get("disclaimer", "")
    generated_at = row.generated_at.strftime("%B %-d, %Y")

    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=inch,
        rightMargin=inch,
        topMargin=inch,
        bottomMargin=1.2 * inch,
    )

    styles = getSampleStyleSheet()
    style_title = styles["Title"]
    style_h2 = styles["Heading2"]
    style_body = styles["BodyText"]
    style_italic = ParagraphStyle(
        "PatientNote",
        parent=style_body,
        fontName="Helvetica-Oblique",
        leftIndent=12,
    )
    style_citation = ParagraphStyle(
        "Citation",
        parent=style_body,
        fontSize=8,
        leftIndent=12,
    )
    style_footer = ParagraphStyle(
        "Footer",
        parent=style_body,
        fontSize=7,
        textColor=(0.4, 0.4, 0.4),
    )

    annotations_by_section: dict[str, list[str]] = {}
    for ann in _parse_annotations(row.patient_annotations):
        annotations_by_section.setdefault(ann.section, []).append(ann.text)

    story: list[Any] = []

    story.append(Paragraph(f"Health Summary — {generated_at}", style_title))
    story.append(Spacer(1, 6))
    story.append(Paragraph(disclaimer, style_footer))
    story.append(Spacer(1, 12))

    for section_key in _SECTION_ORDER:
        label = _SECTION_LABELS[section_key]
        content = row.content_json.get(section_key, "")
        story.append(Paragraph(label, style_h2))
        story.append(Paragraph(escape(content) or "None", style_body))
        for note_text in annotations_by_section.get(section_key, []):
            story.append(Paragraph(f"Patient note: {escape(note_text)}", style_italic))
        story.append(Spacer(1, 6))

    citations: list[dict[str, Any]] = row.content_json.get("citations", [])
    if citations:
        story.append(Paragraph("Citations", style_h2))
        for i, c in enumerate(citations, start=1):
            line = (
                f"[{i}] {c.get('value')} {c.get('unit')} — "
                f"{c.get('collection_date')} (record {c.get('source_record_id')})"
            )
            story.append(Paragraph(line, style_citation))
        story.append(Spacer(1, 6))

    def _add_footer(canvas: Any, doc: Any) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColorRGB(0.4, 0.4, 0.4)
        canvas.drawString(inch, 0.6 * inch, disclaimer)
        canvas.restoreState()

    doc.build(story, onFirstPage=_add_footer, onLaterPages=_add_footer)
    return buf.getvalue()
