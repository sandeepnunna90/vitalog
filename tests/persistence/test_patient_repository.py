"""Unit tests for PatientRepository — no network calls, Supabase client is mocked."""

from __future__ import annotations

import uuid
from datetime import date
from unittest.mock import MagicMock

from src.persistence.models import PatientRow
from src.persistence.patient_repository import PatientRepository

_PATIENT_ID = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
_API_KEY = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
_AUTH_USER_ID = "google-oauth2|123456789"

_ROW = {
    "patient_id": str(_PATIENT_ID),
    "name": "Test Patient",
    "dob": "1980-06-15",
    "created_at": "2024-01-01T00:00:00",
    "auth_user_id": _AUTH_USER_ID,
    "api_key": str(_API_KEY),
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


def test_get_by_api_key_returns_row() -> None:
    """get_by_api_key() returns a PatientRow when the api_key matches."""
    repo = PatientRepository(_mock_client([_ROW]))
    result = repo.get_by_api_key(_API_KEY)

    assert result is not None
    assert result.patient_id == _PATIENT_ID
    assert result.api_key == _API_KEY


def test_get_by_api_key_returns_none_when_not_found() -> None:
    repo = PatientRepository(_mock_client([]))
    assert repo.get_by_api_key(_API_KEY) is None


def test_upsert_from_auth_returns_existing_row() -> None:
    """upsert_from_auth() returns the existing row when auth_user_id already exists."""
    repo = PatientRepository(_mock_client([_ROW]))
    result = repo.upsert_from_auth(_AUTH_USER_ID, "New Name")

    assert result.patient_id == _PATIENT_ID
    assert result.auth_user_id == _AUTH_USER_ID


def test_upsert_from_auth_inserts_new_row() -> None:
    """upsert_from_auth() inserts a new row when auth_user_id is not found."""
    new_id = uuid.uuid4()
    new_api_key = uuid.uuid4()
    new_row = {
        "patient_id": str(new_id),
        "name": "New User",
        "dob": None,
        "created_at": "2026-01-01T00:00:00",
        "auth_user_id": "google|new",
        "api_key": str(new_api_key),
    }
    client = MagicMock()
    # select returns empty (no existing row)
    client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
    # insert returns the new row
    client.table.return_value.insert.return_value.execute.return_value.data = [new_row]

    repo = PatientRepository(client)
    result = repo.upsert_from_auth("google|new", "New User")

    assert result.patient_id == new_id
    assert result.api_key == new_api_key
    client.table.return_value.insert.assert_called_once()
