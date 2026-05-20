"""Repository for patient records."""

from __future__ import annotations

import uuid

from src.persistence.models import PatientRow


_TABLE = "patient"


class PatientRepository:
    def __init__(self, client: object) -> None:
        self._client = client  # type: ignore[assignment]

    def get(self, patient_id: uuid.UUID) -> PatientRow | None:
        data = (
            self._client.table(_TABLE)
            .select("*")
            .eq("patient_id", str(patient_id))
            .execute()
            .data
        )
        if not data:
            return None
        return PatientRow.model_validate(data[0], strict=False)
