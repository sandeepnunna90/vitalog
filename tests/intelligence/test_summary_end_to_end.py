"""End-to-end integration test for SummaryGenerator (F5).

Requires ANTHROPIC_API_KEY and live Supabase connection.
Run with: pytest -m integration tests/intelligence/test_summary_end_to_end.py -v
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from unittest.mock import MagicMock

import pytest

from src.intelligence.summary_generator import DISCLAIMER, SummaryGenerator
from src.intelligence.summary_schemas import Summary
from src.persistence.models import BiomarkerRecordRow
from src.reference_data import MARK_PATIENT_ID

_RECORD_ID_1 = uuid.uuid4()
_RECORD_ID_2 = uuid.uuid4()
_RECORD_ID_3 = uuid.uuid4()

_STUB_RECORDS = [
    BiomarkerRecordRow.model_validate(
        {
            "record_id": _RECORD_ID_1,
            "patient_id": MARK_PATIENT_ID,
            "document_id": None,
            "canonical_biomarker_id": "hba1c",
            "pending_taxonomy_id": None,
            "original_name": "HbA1c",
            "original_value": "6.8",
            "original_unit": "%",
            "original_range": None,
            "canonical_value": 6.8,
            "canonical_unit": "%",
            "collection_date": date(2026, 3, 12),
            "lab_source": "Quest Diagnostics",
            "extraction_confidence": 98.0,
            "verified_by": "auto",
            "created_at": datetime(2026, 3, 12, 10, 0, 0),
        }
    ),
    BiomarkerRecordRow.model_validate(
        {
            "record_id": _RECORD_ID_2,
            "patient_id": MARK_PATIENT_ID,
            "document_id": None,
            "canonical_biomarker_id": "ldl_cholesterol",
            "pending_taxonomy_id": None,
            "original_name": "LDL Cholesterol",
            "original_value": "112",
            "original_unit": "mg/dL",
            "original_range": None,
            "canonical_value": 112.0,
            "canonical_unit": "mg/dL",
            "collection_date": date(2026, 3, 12),
            "lab_source": "Quest Diagnostics",
            "extraction_confidence": 98.0,
            "verified_by": "auto",
            "created_at": datetime(2026, 3, 12, 10, 0, 0),
        }
    ),
    BiomarkerRecordRow.model_validate(
        {
            "record_id": _RECORD_ID_3,
            "patient_id": MARK_PATIENT_ID,
            "document_id": None,
            "canonical_biomarker_id": "tsh",
            "pending_taxonomy_id": None,
            "original_name": "TSH",
            "original_value": "2.1",
            "original_unit": "mIU/L",
            "original_range": None,
            "canonical_value": 2.1,
            "canonical_unit": "mIU/L",
            "collection_date": date(2026, 3, 12),
            "lab_source": "Quest Diagnostics",
            "extraction_confidence": 98.0,
            "verified_by": "auto",
            "created_at": datetime(2026, 3, 12, 10, 0, 0),
        }
    ),
]


@pytest.mark.integration
def test_summary_generate_mark() -> None:
    """Full generate() against live API with stub repo returning 3 known records.

    Asserts: is_fallback=False, disclaimer present verbatim, citation_count > 0.
    """
    from src.gateway.gateway import Gateway

    gateway = Gateway()

    repo = MagicMock()
    repo.list_for_patient.return_value = _STUB_RECORDS

    gen = SummaryGenerator(gateway=gateway, biomarker_repo=repo)
    summary = gen.generate(MARK_PATIENT_ID)

    assert isinstance(summary, Summary)
    assert summary.is_fallback is False, "Unexpected fallback; sections may be empty"
    assert summary.disclaimer == DISCLAIMER
    assert summary.citation_count > 0
    assert summary.patient_id == MARK_PATIENT_ID
