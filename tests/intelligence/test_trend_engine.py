"""Unit tests for F1 — TrendEngine."""

from __future__ import annotations

import subprocess
import uuid
from datetime import date, datetime
from unittest.mock import MagicMock

from src.intelligence.trend_engine import TrendEngine
from src.persistence.models import BiomarkerRecordRow

_PATIENT_ID = uuid.uuid4()
_CANONICAL_ID = "hba1c"


def _make_row(**kwargs: object) -> BiomarkerRecordRow:
    defaults: dict[str, object] = {
        "record_id": uuid.uuid4(),
        "patient_id": _PATIENT_ID,
        "document_id": None,
        "canonical_biomarker_id": _CANONICAL_ID,
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
    defaults.update(kwargs)
    return BiomarkerRecordRow.model_validate(defaults)


def _make_engine(rows: list[BiomarkerRecordRow]) -> TrendEngine:
    repo = MagicMock()
    repo.find_by_canonical_id.return_value = rows
    return TrendEngine(biomarker_repo=repo)


# ── Sorting ───────────────────────────────────────────────────────────────────


def test_sorted_ascending_by_date() -> None:
    rows = [
        _make_row(collection_date=date(2026, 6, 1)),
        _make_row(collection_date=date(2026, 1, 1)),
        _make_row(collection_date=date(2026, 3, 15)),
    ]
    engine = _make_engine(rows)
    result = engine.get_trend(_PATIENT_ID, _CANONICAL_ID)
    dates = [p.collection_date for p in result.points]
    assert dates == sorted(dates)


# ── pending_user filtering ────────────────────────────────────────────────────


def test_pending_user_excluded() -> None:
    rows = [
        _make_row(verified_by="auto"),
        _make_row(verified_by="pending_user"),
    ]
    engine = _make_engine(rows)
    result = engine.get_trend(_PATIENT_ID, _CANONICAL_ID)
    assert len(result.points) == 1
    assert all(p.verified_by != "pending_user" for p in result.points)


def test_pending_review_count() -> None:
    rows = [
        _make_row(verified_by="auto"),
        _make_row(verified_by="pending_user"),
        _make_row(verified_by="pending_user"),
    ]
    engine = _make_engine(rows)
    result = engine.get_trend(_PATIENT_ID, _CANONICAL_ID)
    assert result.pending_review_count == 2


def test_only_pending_returns_empty() -> None:
    rows = [_make_row(verified_by="pending_user") for _ in range(3)]
    engine = _make_engine(rows)
    result = engine.get_trend(_PATIENT_ID, _CANONICAL_ID)
    assert result.points == []
    assert result.pending_review_count == 3


def test_no_records_empty_trend() -> None:
    engine = _make_engine([])
    result = engine.get_trend(_PATIENT_ID, _CANONICAL_ID)
    assert result.points == []
    assert result.pending_review_count == 0


# ── Null field exclusions ─────────────────────────────────────────────────────


def test_null_canonical_value_excluded() -> None:
    rows = [
        _make_row(canonical_value=None),
        _make_row(canonical_value=6.8),
    ]
    engine = _make_engine(rows)
    result = engine.get_trend(_PATIENT_ID, _CANONICAL_ID)
    assert len(result.points) == 1


def test_null_collection_date_excluded() -> None:
    rows = [
        _make_row(collection_date=None),
        _make_row(collection_date=date(2026, 3, 12)),
    ]
    engine = _make_engine(rows)
    result = engine.get_trend(_PATIENT_ID, _CANONICAL_ID)
    assert len(result.points) == 1


# ── verified_by values ────────────────────────────────────────────────────────


def test_auto_user_admin_all_accepted() -> None:
    rows = [
        _make_row(verified_by="auto", collection_date=date(2026, 1, 1)),
        _make_row(verified_by="user", collection_date=date(2026, 2, 1)),
        _make_row(verified_by="admin", collection_date=date(2026, 3, 1)),
    ]
    engine = _make_engine(rows)
    result = engine.get_trend(_PATIENT_ID, _CANONICAL_ID)
    assert len(result.points) == 3


# ── Bands ─────────────────────────────────────────────────────────────────────


def test_bands_populated_from_guideline() -> None:
    engine = _make_engine([_make_row()])
    result = engine.get_trend(_PATIENT_ID, _CANONICAL_ID, patient_conditions=["T2D"])
    assert len(result.bands) > 0


# ── AC6: no LLM imports ───────────────────────────────────────────────────────


def test_no_anthropic_import() -> None:
    completed = subprocess.run(
        ["grep", "-r", r"anthropic\|Gateway", "src/intelligence/trend_engine.py"],
        capture_output=True,
        text=True,
        cwd="/Users/sandeepnunna/workspace/100x-Engineers/applications/vitalog",
    )
    assert completed.stdout.strip() == "", (
        f"Found LLM references in trend_engine.py: {completed.stdout}"
    )
