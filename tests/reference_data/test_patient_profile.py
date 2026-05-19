"""Unit tests for G2 — Mark Capstone patient profile loader.

All tests are purely in-process: no network calls, no Supabase writes.
"""

from __future__ import annotations

import re

from src.reference_data import load_biomarker_groups
from src.reference_data.patient_profile import MARK_PATIENT_ID, load_patient_profile
from src.reference_data.patient_profile_schemas import PatientProfile


def test_profile_loads_as_patient_profile() -> None:
    profile = load_patient_profile()
    assert isinstance(profile, PatientProfile)


def test_patient_id_matches_constant() -> None:
    profile = load_patient_profile()
    assert profile.patient_id == MARK_PATIENT_ID


def test_conditions_are_exact_and_in_groups() -> None:
    profile = load_patient_profile()
    assert profile.conditions == ["T2D", "HTN", "hypothyroidism"]
    groups = load_biomarker_groups()["conditions"]
    for code in profile.conditions:
        assert code in groups, f"{code!r} not in biomarker_groups.json"


def test_profile_version_is_1_1_0() -> None:
    profile = load_patient_profile()
    assert profile.profile_version == "1.1.0"


def test_profile_has_no_medications_or_allergies() -> None:
    profile = load_patient_profile()
    assert not hasattr(profile, "medications")
    assert not hasattr(profile, "allergies")


def test_profile_version_hash_is_sha256_hex() -> None:
    profile = load_patient_profile()
    assert re.fullmatch(r"[0-9a-f]{64}", profile.profile_version_hash) is not None


def test_load_is_cached() -> None:
    p1 = load_patient_profile()
    p2 = load_patient_profile()
    assert p1 is p2


def test_no_supabase_or_anthropic_in_loader() -> None:
    import importlib.util
    from pathlib import Path

    loader_path = Path(__file__).parent.parent.parent / "src/reference_data/patient_profile.py"
    src = loader_path.read_text()
    assert "supabase" not in src
    assert "anthropic" not in src
    assert importlib.util.find_spec("src.reference_data.patient_profile") is not None
