"""Unit tests for SummaryAnnotator (F6 ACs 1)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from src.intelligence.annotator import SummaryAnnotator
from src.intelligence.summary_schemas import Summary
from src.persistence.models import SummaryRow

_PATIENT_ID = uuid.UUID("7f3b1c5e-4d2a-4e8f-b6c9-1a2b3c4d5e6f")
_SUMMARY_ID = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")


def _make_summary() -> Summary:
    from src.gateway.citation_schemas import Citation

    return Summary(
        patient_id=_PATIENT_ID,
        conditions_section="Type 2 Diabetes",
        medications_section="Metformin 1000mg",
        results_section="HbA1c: 6.8%",
        trends_section="HbA1c improved.",
        data_gaps_section="No lipid panel on record.",
        patient_notes="",
        citations=[
            Citation(
                value=6.8,
                unit="%",
                collection_date=datetime(2026, 3, 12).date(),
                source_record_id=uuid.uuid4(),
            )
        ],
        disclaimer="This summary was prepared by Vitalog from patient-uploaded records. "
        "It is not a medical document and does not constitute medical advice. "
        "Please verify all information with your healthcare provider.",
        prompt_version="v2",
        citation_count=1,
        is_fallback=False,
    )


def _make_row(patient_annotations: str | None = None) -> SummaryRow:
    return SummaryRow(
        summary_id=_SUMMARY_ID,
        patient_id=_PATIENT_ID,
        generated_at=datetime(2026, 5, 18, 10, 0, 0),
        content_json={"conditions_section": "Type 2 Diabetes", "disclaimer": "Disclaimer."},
        patient_annotations=patient_annotations,
        exported_formats=[],
    )


def _make_repo(row: SummaryRow | None = None) -> MagicMock:
    repo = MagicMock()
    repo.add.return_value = _make_row()
    repo.get.return_value = row
    repo.update_annotations.return_value = _make_row()
    return repo


def test_persist_calls_repo_add() -> None:
    """persist() calls summary_repo.add() with content_json from the Summary model."""
    summary = _make_summary()
    repo = _make_repo()
    annotator = SummaryAnnotator(summary_repo=repo)

    annotator.persist(summary)

    repo.add.assert_called_once()
    call_arg = repo.add.call_args[0][0]
    assert call_arg.patient_id == _PATIENT_ID
    assert "conditions_section" in call_arg.content_json


def test_persist_returns_row_with_summary_id() -> None:
    """persist() returns SummaryRow with a summary_id."""
    summary = _make_summary()
    repo = _make_repo()
    annotator = SummaryAnnotator(summary_repo=repo)

    row = annotator.persist(summary)

    assert isinstance(row, SummaryRow)
    assert row.summary_id == _SUMMARY_ID


def test_persist_emits_audit_event() -> None:
    """persist() calls audit_repo.record with event_type='summary_persisted'."""
    summary = _make_summary()
    repo = _make_repo()
    audit_repo = MagicMock()
    annotator = SummaryAnnotator(summary_repo=repo, audit_repo=audit_repo)

    annotator.persist(summary)

    audit_repo.record.assert_called_once()
    kwargs = audit_repo.record.call_args.kwargs
    assert kwargs["event_type"] == "summary_persisted"


def test_add_note_appends_annotation() -> None:
    """add_note() fetches the row, appends annotation, and calls update_annotations()."""
    existing_row = _make_row(patient_annotations=None)
    repo = _make_repo(row=existing_row)
    annotator = SummaryAnnotator(summary_repo=repo)

    annotator.add_note(_SUMMARY_ID, "conditions_section", "Started statin 2026-02-01")

    repo.update_annotations.assert_called_once()
    serialized = repo.update_annotations.call_args[0][1]
    parsed = json.loads(serialized)
    assert len(parsed) == 1
    assert parsed[0]["section"] == "conditions_section"
    assert parsed[0]["text"] == "Started statin 2026-02-01"


def test_add_note_invalid_section_raises() -> None:
    """add_note() raises ValueError for an unrecognised section name."""
    repo = _make_repo(row=_make_row())
    annotator = SummaryAnnotator(summary_repo=repo)

    with pytest.raises(ValueError, match="Invalid section"):
        annotator.add_note(_SUMMARY_ID, "nonexistent_section", "some note")


def test_add_note_unknown_summary_raises() -> None:
    """add_note() raises ValueError when the summary_id is not found."""
    repo = _make_repo(row=None)
    annotator = SummaryAnnotator(summary_repo=repo)

    with pytest.raises(ValueError, match="not found"):
        annotator.add_note(_SUMMARY_ID, "conditions_section", "note")


def test_add_note_preserves_existing_annotations() -> None:
    """A second add_note() call appends to existing annotations, not replaces them."""
    first_annotation = json.dumps(
        [
            {
                "annotation_id": str(uuid.uuid4()),
                "section": "medications_section",
                "text": "First note",
                "created_at": "2026-05-18T09:00:00",
            }
        ]
    )
    existing_row = _make_row(patient_annotations=first_annotation)
    updated_row = _make_row(patient_annotations=first_annotation)
    repo = _make_repo(row=existing_row)
    repo.update_annotations.return_value = updated_row
    annotator = SummaryAnnotator(summary_repo=repo)

    annotator.add_note(_SUMMARY_ID, "conditions_section", "Second note")

    serialized = repo.update_annotations.call_args[0][1]
    parsed = json.loads(serialized)
    assert len(parsed) == 2
    assert parsed[0]["text"] == "First note"
    assert parsed[1]["text"] == "Second note"
