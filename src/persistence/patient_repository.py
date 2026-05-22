"""Repository for patient records."""

from __future__ import annotations

import uuid

from supabase import Client

from src.persistence.models import PatientAuthCreate, PatientRow

_TABLE = "patient"


class PatientRepository:
    def __init__(self, client: Client) -> None:
        self._client = client

    def get(self, patient_id: uuid.UUID) -> PatientRow | None:
        data = (
            self._client.table(_TABLE).select("*").eq("patient_id", str(patient_id)).execute().data
        )
        if not data:
            return None
        return PatientRow.model_validate(data[0], strict=False)

    def get_by_api_key(self, api_key: uuid.UUID) -> PatientRow | None:
        data = self._client.table(_TABLE).select("*").eq("api_key", str(api_key)).execute().data
        if not data:
            return None
        return PatientRow.model_validate(data[0], strict=False)

    def upsert_from_auth(self, auth_user_id: str, name: str) -> PatientRow:
        data = (
            self._client.table(_TABLE).select("*").eq("auth_user_id", auth_user_id).execute().data
        )
        if data:
            return PatientRow.model_validate(data[0], strict=False)
        new = PatientAuthCreate(
            patient_id=uuid.uuid4(),
            name=name,
            auth_user_id=auth_user_id,
            api_key=uuid.uuid4(),
        )
        result = self._client.table(_TABLE).insert(new.model_dump(mode="json")).execute().data
        return PatientRow.model_validate(result[0], strict=False)
