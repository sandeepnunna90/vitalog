"""Pydantic models for the hardcoded Mark Capstone patient profile (G2)."""

from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict


class _Base(BaseModel):
    model_config = ConfigDict(strict=True)


class PatientProfile(_Base):
    patient_id: uuid.UUID
    name: str
    dob: date
    profile_version: str
    profile_version_hash: str  # SHA-256 of raw JSON bytes, injected by loader
    note: str  # human-readable label (e.g. "DEMO PROFILE — synthetic data")
    conditions: list[str]  # condition codes matching biomarker_groups.json condition keys
