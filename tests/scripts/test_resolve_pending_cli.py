"""Unit tests for the resolve_pending admin CLI."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.resolve_pending import cmd_confirm, cmd_list, cmd_reject
from src.persistence.models import PendingTaxonomyEntryRow


def _pending_row(**kwargs: object) -> PendingTaxonomyEntryRow:
    defaults: dict[str, object] = {
        "pending_id": uuid.uuid4(),
        "document_id": None,
        "raw_name": "Lipase",
        "raw_unit": "U/L",
        "candidate_loinc_codes": [],
        "proposed_canonical_name": None,
        "similarity_to_existing": {},
        "status": "pending",
        "resolved_at": None,
        "resolved_by": None,
    }
    defaults.update(kwargs)
    return PendingTaxonomyEntryRow.model_validate(defaults)


# ── cmd_list ──────────────────────────────────────────────────────────────────


def test_list_prints_empty_message_when_no_pending(capsys: pytest.CaptureFixture[str]) -> None:
    args = MagicMock()
    with (
        patch("scripts.resolve_pending._get_client"),
        patch("scripts.resolve_pending.TaxonomyRepository") as mock_repo,
    ):
        mock_repo.return_value.list_pending.return_value = []
        cmd_list(args)

    out = capsys.readouterr().out
    assert "empty" in out.lower()


def test_list_prints_pending_entries(capsys: pytest.CaptureFixture[str]) -> None:
    pid = uuid.uuid4()
    row = _pending_row(pending_id=pid, raw_name="Lipase")
    args = MagicMock()
    with (
        patch("scripts.resolve_pending._get_client"),
        patch("scripts.resolve_pending.TaxonomyRepository") as mock_repo,
    ):
        mock_repo.return_value.list_pending.return_value = [row]
        cmd_list(args)

    out = capsys.readouterr().out
    assert "Lipase" in out
    assert str(pid) in out


# ── cmd_confirm ───────────────────────────────────────────────────────────────


def test_confirm_resolves_pending_and_updates_records(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pid = uuid.uuid4()
    row = _pending_row(pending_id=pid, raw_name="Lipase")

    args = MagicMock()
    args.pending_id = str(pid)
    args.canonical = "hba1c"

    taxonomy_file = tmp_path / "biomarker_taxonomy.json"
    taxonomy_file.write_text(
        json.dumps(
            [
                {
                    "vitalog_id": "hba1c",
                    "canonical_name": "Hemoglobin A1c",
                    "loinc_code": "4548-4",
                    "ucum_unit": "%",
                    "unit_conversions": [],
                    "aliases": ["HbA1c"],
                    "conditions": [],
                    "guideline_ranges": {},
                    "guideline_citations": {},
                    "verification_tier": 1,
                    "verified": True,
                }
            ]
        ),
        encoding="utf-8",
    )

    with (
        patch("scripts.resolve_pending._get_client"),
        patch("scripts.resolve_pending.TaxonomyRepository") as mock_taxo_repo,
        patch("scripts.resolve_pending.BiomarkerRepository") as mock_bio_repo,
        patch("scripts.resolve_pending.add_alias") as mock_add_alias,
    ):
        mock_taxo_repo.return_value.list_pending.return_value = [row]
        mock_bio_repo.return_value.resolve_pending_records.return_value = 3
        mock_taxo_repo.return_value.resolve_pending.return_value = row

        cmd_confirm(args)

    mock_bio_repo.return_value.resolve_pending_records.assert_called_once_with(pid, "hba1c")
    mock_add_alias.assert_called_once_with("hba1c", "Lipase")
    mock_taxo_repo.return_value.resolve_pending.assert_called_once_with(
        pid, status="confirmed", resolved_by="admin"
    )
    out = capsys.readouterr().out
    assert "Confirmed" in out


def test_confirm_exits_if_pending_not_found(capsys: pytest.CaptureFixture[str]) -> None:
    args = MagicMock()
    args.pending_id = str(uuid.uuid4())
    args.canonical = "hba1c"

    with (
        patch("scripts.resolve_pending._get_client"),
        patch("scripts.resolve_pending.TaxonomyRepository") as mock_repo,
        patch("scripts.resolve_pending.BiomarkerRepository"),
    ):
        mock_repo.return_value.list_pending.return_value = []
        with pytest.raises(SystemExit):
            cmd_confirm(args)


def test_confirm_tolerates_duplicate_alias(capsys: pytest.CaptureFixture[str]) -> None:
    pid = uuid.uuid4()
    row = _pending_row(pending_id=pid, raw_name="HbA1c")

    args = MagicMock()
    args.pending_id = str(pid)
    args.canonical = "hba1c"

    with (
        patch("scripts.resolve_pending._get_client"),
        patch("scripts.resolve_pending.TaxonomyRepository") as mock_taxo_repo,
        patch("scripts.resolve_pending.BiomarkerRepository") as mock_bio_repo,
        patch("scripts.resolve_pending.add_alias", side_effect=ValueError("already exists")),
    ):
        mock_taxo_repo.return_value.list_pending.return_value = [row]
        mock_bio_repo.return_value.resolve_pending_records.return_value = 0
        mock_taxo_repo.return_value.resolve_pending.return_value = row

        cmd_confirm(args)  # must not raise

    out = capsys.readouterr().out
    assert "Confirmed" in out


# ── cmd_reject ────────────────────────────────────────────────────────────────


def test_reject_calls_resolve_with_rejected_status(capsys: pytest.CaptureFixture[str]) -> None:
    pid = uuid.uuid4()
    args = MagicMock()
    args.pending_id = str(pid)

    with (
        patch("scripts.resolve_pending._get_client"),
        patch("scripts.resolve_pending.TaxonomyRepository") as mock_repo,
    ):
        mock_repo.return_value.resolve_pending.return_value = _pending_row(
            pending_id=pid, status="rejected"
        )
        cmd_reject(args)

    mock_repo.return_value.resolve_pending.assert_called_once_with(
        pid, status="rejected", resolved_by="admin"
    )
    out = capsys.readouterr().out
    assert "Rejected" in out
