"""Unit tests for G2 — Mark Capstone patient profile loader.

All tests are purely in-process: no network calls, no Supabase writes.
"""

from __future__ import annotations

import re
from datetime import date

from src.reference_data import load_condition_biomarker_map
from src.reference_data.patient_profile import MARK_PATIENT_ID, load_patient_profile
from src.reference_data.patient_profile_schemas import PatientProfile


def test_profile_loads_as_patient_profile() -> None:
    profile = load_patient_profile()
    assert isinstance(profile, PatientProfile)


def test_patient_id_matches_constant() -> None:
    profile = load_patient_profile()
    assert profile.patient_id == MARK_PATIENT_ID


def test_conditions_are_exact_and_in_map() -> None:
    profile = load_patient_profile()
    assert profile.conditions == ["T2D", "HTN", "hypothyroidism"]
    condition_map = load_condition_biomarker_map()["conditions"]
    for code in profile.conditions:
        assert code in condition_map, f"{code!r} not in condition_biomarker_map.json"


def test_rosuvastatin_present_with_correct_start_date() -> None:
    profile = load_patient_profile()
    statins = [m for m in profile.medications if m.name == "Rosuvastatin"]
    assert len(statins) == 1
    assert statins[0].start_date == date(2026, 2, 15)


def test_penicillin_allergy_present() -> None:
    profile = load_patient_profile()
    substances = [a.substance for a in profile.allergies]
    assert "Penicillin" in substances


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
