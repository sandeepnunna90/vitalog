"""Unit tests for PatientRepository — no network calls, Supabase client is mocked."""

from __future__ import annotations

import uuid
from datetime import date
from unittest.mock import MagicMock

from src.persistence.models import PatientRow
from src.persistence.patient_repository import PatientRepository

_PATIENT_ID = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")

_ROW = {
    "patient_id": str(_PATIENT_ID),
    "name": "Test Patient",
    "dob": "1980-06-15",
    "created_at": "2024-01-01T00:00:00",
}


def _mock_client(rows: list[dict]) -> MagicMock:
    client = MagicMock()
    (client.table.return_value.select.return_value.eq.return_value.execute.return_value.data) = rows
    return client


def test_get_returns_patient_row() -> None:
    """get() with a matching row returns a PatientRow with correct fields."""
    repo = PatientRepository(_mock_client([_ROW]))
    result = repo.get(_PATIENT_ID)

    assert result is not None
    assert isinstance(result, PatientRow)
    assert result.patient_id == _PATIENT_ID
    assert result.name == "Test Patient"
    assert result.dob == date(1980, 6, 15)


def test_get_returns_none_when_not_found() -> None:
    """get() with no matching row returns None."""
    repo = PatientRepository(_mock_client([]))
    result = repo.get(_PATIENT_ID)

    assert result is None


def test_get_queries_correct_table_and_id() -> None:
    """get() calls the Supabase client with the right table and patient_id filter."""
    client = _mock_client([_ROW])
    repo = PatientRepository(client)
    repo.get(_PATIENT_ID)

    client.table.assert_called_once_with("patient")
    client.table.return_value.select.assert_called_once_with("*")
    client.table.return_value.select.return_value.eq.assert_called_once_with(
        "patient_id", str(_PATIENT_ID)
    )
