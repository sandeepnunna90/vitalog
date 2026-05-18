"""Markdown export for F6 — GitHub-flavored markdown."""

from __future__ import annotations

from typing import Any

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


def export_markdown(row: SummaryRow) -> bytes:
    """Render a SummaryRow to UTF-8 GitHub-flavored markdown bytes."""
    content = row.content_json
    disclaimer = content.get("disclaimer", "")
    generated_at = row.generated_at.isoformat()

    lines: list[str] = []
    lines.append(f"# Health Summary — {row.generated_at.strftime('%B %-d, %Y')}")
    lines.append("")
    lines.append(f"> {disclaimer}")
    lines.append("")
    lines.append(f"Generated: {generated_at}")
    lines.append("")

    annotations_by_section: dict[str, list[Any]] = {}
    for ann in _parse_annotations(row.patient_annotations):
        annotations_by_section.setdefault(ann.section, []).append(ann)

    for section_key in _SECTION_ORDER:
        label = _SECTION_LABELS[section_key]
        body = content.get(section_key, "")
        lines.append(f"## {label}")
        lines.append("")
        lines.append(body or "_None_")
        lines.append("")
        for ann in annotations_by_section.get(section_key, []):
            lines.append(f"> **Patient note:** {ann.text} _({ann.created_at[:10]})_")
            lines.append("")

    citations: list[dict[str, Any]] = content.get("citations", [])
    if citations:
        lines.append("---")
        lines.append("")
        lines.append("## Citations")
        lines.append("")
        for i, c in enumerate(citations, start=1):
            lines.append(
                f"[{i}] {c.get('value')} {c.get('unit')} — "
                f"{c.get('collection_date')} (record `{c.get('source_record_id')}`)"
            )
        lines.append("")

    return "\n".join(lines).encode("utf-8")
