"""Loader for the hardcoded Mark Capstone patient profile (G2).

The profile lives in reference_data/mark_profile.json and is never read from
Supabase at capstone scope — see CLAUDE.md Gotchas and architecture §6.1.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from functools import lru_cache

from src._paths import PROJECT_ROOT
from src.reference_data.patient_profile_schemas import PatientProfile

_MARK_PROFILE_PATH = PROJECT_ROOT / "reference_data" / "mark_profile.json"

MARK_PATIENT_ID = uuid.UUID("7f3b1c5e-4d2a-4e8f-b6c9-1a2b3c4d5e6f")


@lru_cache(maxsize=1)
def load_patient_profile() -> PatientProfile:
    """Load and return Mark's patient profile (cached after first call).

    Injects `profile_version_hash` (SHA-256 of raw JSON bytes) so callers
    can record an audit-log event without re-reading the file.
    """
    raw = _MARK_PROFILE_PATH.read_bytes()
    data = json.loads(raw)
    data["profile_version_hash"] = hashlib.sha256(raw).hexdigest()
    return PatientProfile.model_validate(data, strict=False)
