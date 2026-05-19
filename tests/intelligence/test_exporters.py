"""Unit tests for F6 exporters (PDF, Markdown, JSON) and export_summary() dispatch."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from src.intelligence.exporter import export_summary
from src.intelligence.exporters.json_exporter import export_json
from src.intelligence.exporters.markdown_exporter import export_markdown
from src.intelligence.exporters.pdf_exporter import export_pdf
from src.persistence.models import SummaryRow

_PATIENT_ID = uuid.UUID("7f3b1c5e-4d2a-4e8f-b6c9-1a2b3c4d5e6f")
_SUMMARY_ID = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
_RECORD_ID = uuid.UUID("11112222-3333-4444-5555-666677778888")

_DISCLAIMER = (
    "This summary was prepared by Vitalog from patient-uploaded records. "
    "It is not a medical document and does not constitute medical advice. "
    "Please verify all information with your healthcare provider."
)

_CONTENT_JSON = {
    "patient_id": str(_PATIENT_ID),
    "conditions_section": "Type 2 Diabetes, Hypertension",
    "results_section": "HbA1c: 6.8% (March 12, 2026)",
    "trends_section": "HbA1c decreased from 7.1% to 6.8% over 6 months.",
    "data_gaps_section": "No lipid panel on record.",
    "patient_notes": "",
    "citations": [
        {
            "value": 6.8,
            "unit": "%",
            "collection_date": "2026-03-12",
            "source_record_id": str(_RECORD_ID),
        }
    ],
    "disclaimer": _DISCLAIMER,
    "prompt_version": "v3",
    "citation_count": 1,
    "is_fallback": False,
}


def _make_summary_row(patient_annotations: str | None = None) -> SummaryRow:
    return SummaryRow(
        summary_id=_SUMMARY_ID,
        patient_id=_PATIENT_ID,
        generated_at=datetime(2026, 5, 18, 10, 0, 0),
        content_json=_CONTENT_JSON,
        patient_annotations=patient_annotations,
        exported_formats=[],
    )


def _make_repo(row: SummaryRow | None = None) -> MagicMock:
    repo = MagicMock()
    repo.get.return_value = row if row is not None else _make_summary_row()
    return repo


# ── PDF ───────────────────────────────────────────────────────────────────────


def test_pdf_export_returns_bytes() -> None:
    """export_pdf() returns non-empty bytes starting with the PDF magic bytes."""
    row = _make_summary_row()
    data = export_pdf(row)
    assert isinstance(data, bytes)
    assert len(data) > 0
    assert data[:4] == b"%PDF"


def test_pdf_has_substantial_content() -> None:
    """PDF with sections and citations has non-trivial size (>1 KB)."""
    row = _make_summary_row()
    data = export_pdf(row)
    assert len(data) > 1000


# ── Markdown ──────────────────────────────────────────────────────────────────


def test_markdown_export_structure() -> None:
    """export_markdown() output contains expected section headings."""
    row = _make_summary_row()
    text = export_markdown(row).decode("utf-8")
    assert "## Active Conditions" in text
    assert "## Biomarker Results" in text
    assert "## Citations" in text
    assert "## Current Medications" not in text


def test_markdown_disclaimer_at_top() -> None:
    """Disclaimer appears in the first 500 characters of markdown output."""
    row = _make_summary_row()
    text = export_markdown(row).decode("utf-8")
    assert "Vitalog" in text[:500]


# ── JSON ──────────────────────────────────────────────────────────────────────


def test_json_export_roundtrip() -> None:
    """export_json() output parses to a dict with all expected top-level keys."""
    row = _make_summary_row()
    data = export_json(row)
    parsed = json.loads(data.decode("utf-8"))
    assert "disclaimer" in parsed
    assert "conditions_section" in parsed
    assert "citations" in parsed
    assert parsed["summary_id"] == str(_SUMMARY_ID)


def test_json_annotations_included() -> None:
    """Annotations are present in JSON output when patient_annotations is populated."""
    annotation = json.dumps(
        [
            {
                "annotation_id": str(uuid.uuid4()),
                "section": "conditions_section",
                "text": "Started statin 2026-02-01",
                "created_at": "2026-05-18T09:00:00",
            }
        ]
    )
    row = _make_summary_row(patient_annotations=annotation)
    data = export_json(row)
    parsed = json.loads(data.decode("utf-8"))
    assert len(parsed["patient_annotations"]) == 1
    assert parsed["patient_annotations"][0]["text"] == "Started statin 2026-02-01"


# ── Dispatch ──────────────────────────────────────────────────────────────────


def test_export_summary_dispatch_pdf() -> None:
    """export_summary(..., 'pdf') returns PDF bytes."""
    repo = _make_repo()
    data = export_summary(_SUMMARY_ID, "pdf", repo)
    assert data[:4] == b"%PDF"


def test_export_summary_unknown_format_raises() -> None:
    """export_summary() raises ValueError for an unsupported format."""
    repo = _make_repo()
    with pytest.raises(ValueError, match="Unsupported format"):
        export_summary(_SUMMARY_ID, "docx", repo)
