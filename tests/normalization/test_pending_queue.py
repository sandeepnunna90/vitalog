"""Unit tests for E2 — PendingQueue and TaxonomyEditor."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.normalization.pending_queue import PendingQueue
from src.normalization.taxonomy_editor import add_alias
from src.persistence.models import PendingTaxonomyEntryRow


def _make_row(**kwargs: object) -> PendingTaxonomyEntryRow:
    defaults: dict[str, object] = {
        "pending_id": uuid.uuid4(),
        "document_id": None,
        "raw_name": "Unknown Marker",
        "raw_unit": None,
        "candidate_loinc_codes": [],
        "proposed_canonical_name": None,
        "similarity_to_existing": {},
        "status": "pending",
        "resolved_at": None,
        "resolved_by": None,
    }
    defaults.update(kwargs)
    return PendingTaxonomyEntryRow.model_validate(defaults)


# ── PendingQueue.enqueue ──────────────────────────────────────────────────────


def test_enqueue_calls_add_pending_with_raw_name() -> None:
    repo = MagicMock()
    repo.add_pending.return_value = _make_row(raw_name="Lipase")
    q = PendingQueue(repo)
    result = q.enqueue("Lipase")
    repo.add_pending.assert_called_once()
    call_arg = repo.add_pending.call_args[0][0]
    assert call_arg.raw_name == "Lipase"
    assert result.raw_name == "Lipase"


def test_enqueue_passes_document_id() -> None:
    doc_id = uuid.uuid4()
    repo = MagicMock()
    repo.add_pending.return_value = _make_row(document_id=doc_id)
    PendingQueue(repo).enqueue("Lipase", document_id=doc_id)
    call_arg = repo.add_pending.call_args[0][0]
    assert call_arg.document_id == doc_id


def test_enqueue_passes_raw_unit() -> None:
    repo = MagicMock()
    repo.add_pending.return_value = _make_row(raw_unit="U/L")
    PendingQueue(repo).enqueue("Lipase", raw_unit="U/L")
    call_arg = repo.add_pending.call_args[0][0]
    assert call_arg.raw_unit == "U/L"


def test_enqueue_empty_loinc_and_similarity() -> None:
    repo = MagicMock()
    repo.add_pending.return_value = _make_row()
    PendingQueue(repo).enqueue("Unknown X")
    call_arg = repo.add_pending.call_args[0][0]
    assert call_arg.candidate_loinc_codes == []
    assert call_arg.similarity_to_existing == {}


def test_enqueue_status_is_pending() -> None:
    repo = MagicMock()
    repo.add_pending.return_value = _make_row(status="pending")
    result = PendingQueue(repo).enqueue("Unknown X")
    assert result.status == "pending"


# ── TaxonomyEditor.add_alias ──────────────────────────────────────────────────


@pytest.fixture()
def tmp_taxonomy(tmp_path: Path) -> Path:
    data = [
        {
            "vitalog_id": "hba1c",
            "canonical_name": "Hemoglobin A1c",
            "loinc_code": "4548-4",
            "ucum_unit": "%",
            "unit_conversions": [],
            "aliases": ["HbA1c", "A1C"],
            "conditions": [],
            "guideline_ranges": {},
            "guideline_citations": {},
            "verification_tier": 1,
            "verified": True,
        }
    ]
    p = tmp_path / "biomarker_taxonomy.json"
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return p


def test_add_alias_appends_to_entry(tmp_taxonomy: Path) -> None:
    with patch("src.normalization.taxonomy_editor._index"):
        add_alias("hba1c", "glycohemoglobin", taxonomy_path=tmp_taxonomy)
    data = json.loads(tmp_taxonomy.read_text())
    assert "glycohemoglobin" in data[0]["aliases"]


def test_add_alias_clears_tier1_cache(tmp_taxonomy: Path) -> None:
    with patch("src.normalization.taxonomy_editor._index") as mock_idx:
        add_alias("hba1c", "new_alias", taxonomy_path=tmp_taxonomy)
        mock_idx.cache_clear.assert_called_once()


def test_add_alias_raises_for_unknown_vitalog_id(tmp_taxonomy: Path) -> None:
    with pytest.raises(ValueError, match="not found"):
        add_alias("nonexistent_id", "some_alias", taxonomy_path=tmp_taxonomy)


def test_add_alias_raises_if_alias_already_exists(tmp_taxonomy: Path) -> None:
    with pytest.raises(ValueError, match="already exists"):
        add_alias("hba1c", "A1C", taxonomy_path=tmp_taxonomy)


def test_add_alias_raises_if_alias_matches_canonical_name(tmp_taxonomy: Path) -> None:
    with pytest.raises(ValueError, match="already exists"):
        add_alias("hba1c", "Hemoglobin A1c", taxonomy_path=tmp_taxonomy)


def test_add_alias_file_is_valid_json_after_write(tmp_taxonomy: Path) -> None:
    with patch("src.normalization.taxonomy_editor._index"):
        add_alias("hba1c", "new_alias", taxonomy_path=tmp_taxonomy)
    data = json.loads(tmp_taxonomy.read_text())
    assert isinstance(data, list)
    assert data[0]["vitalog_id"] == "hba1c"
