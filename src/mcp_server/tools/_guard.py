"""Patient-ID guard — validates against the configured patient UUID.

VITALOG_PATIENT_ID env var sets the accepted UUID at runtime.
Falls back to Mark's hardcoded capstone UUID if the env var is not set.
"""

from __future__ import annotations

import os
import uuid

from src.reference_data.patient_profile import MARK_PATIENT_ID


def _load_accepted_patient_id() -> uuid.UUID:
    raw = os.environ.get("VITALOG_PATIENT_ID")
    if raw:
        try:
            return uuid.UUID(raw)
        except ValueError:
            raise ValueError(f"VITALOG_PATIENT_ID env var is not a valid UUID: {raw!r}") from None
    return MARK_PATIENT_ID


_ACCEPTED_PATIENT_ID: uuid.UUID = _load_accepted_patient_id()
PATIENT_ID: uuid.UUID = _ACCEPTED_PATIENT_ID


def validate_patient_id(patient_id: str) -> uuid.UUID:
    """Return the parsed UUID if patient_id matches the accepted patient.

    Raises ValueError if the UUID is malformed or not registered.
    Accepts the UUID in any standard string form (with or without hyphens).
    """
    try:
        parsed = uuid.UUID(patient_id)
    except ValueError:
        raise ValueError(f"Invalid patient_id format: {patient_id!r}") from None
    if parsed != _ACCEPTED_PATIENT_ID:
        raise ValueError(
            f"patient_id {patient_id!r} is not registered in this system. "
            f"Set VITALOG_PATIENT_ID env var to register a patient UUID."
        )
    return parsed
