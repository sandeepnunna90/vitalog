"""Capstone patient-ID guard — all tools validate against Mark's hardcoded UUID."""

from __future__ import annotations

import uuid

from src.reference_data.patient_profile import MARK_PATIENT_ID

_MARK_ID_STR = str(MARK_PATIENT_ID)


def validate_patient_id(patient_id: str) -> uuid.UUID:
    """Return MARK_PATIENT_ID if patient_id matches; raise ValueError otherwise.

    Accepts the UUID in any standard string form (with or without hyphens).
    """
    try:
        parsed = uuid.UUID(patient_id)
    except ValueError:
        raise ValueError(f"Invalid patient_id format: {patient_id!r}") from None
    if parsed != MARK_PATIENT_ID:
        raise ValueError(
            f"patient_id {patient_id!r} is not registered in this system. "
            "Only the capstone patient profile is supported."
        )
    return parsed
