"""AC1-AC6 — ground-truth JSON structure and content invariants."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.eval.synthesis.content_generator import BIOMARKER_RANGES
from src.eval.synthesis.vendor_templates.quest import generate_report

_REQUIRED_TOP_KEYS = {
    "document_type",
    "lab_source",
    "collection_date",
    "patient_name",
    "patient_dob",
    "biomarkers",
}
_REQUIRED_BIOMARKER_KEYS = {
    "vitalog_id",
    "original_name",
    "original_value",
    "original_unit",
    "original_range",
    "collection_date",
    "lab_source",
}


@pytest.fixture(scope="module")
def ground_truth(tmp_path_factory: pytest.TempPathFactory) -> dict:  # type: ignore[type-arg]
    out = tmp_path_factory.mktemp("gt")
    _, gt_path = generate_report(1, out)
    return json.loads(gt_path.read_text(encoding="utf-8"))


def test_top_level_keys_present(ground_truth: dict) -> None:  # type: ignore[type-arg]
    assert _REQUIRED_TOP_KEYS.issubset(ground_truth.keys())


def test_document_type_is_lab_report(ground_truth: dict) -> None:  # type: ignore[type-arg]
    assert ground_truth["document_type"] == "lab_report"


def test_patient_pii_is_synthetic(ground_truth: dict) -> None:  # type: ignore[type-arg]
    assert ground_truth["patient_name"] == "TEST PATIENT"
    assert ground_truth["patient_dob"] == "1970-01-01"


def test_biomarker_count_matches_ranges(ground_truth: dict) -> None:  # type: ignore[type-arg]
    assert len(ground_truth["biomarkers"]) == len(BIOMARKER_RANGES)


def test_every_biomarker_has_required_keys(ground_truth: dict) -> None:  # type: ignore[type-arg]
    for entry in ground_truth["biomarkers"]:
        assert _REQUIRED_BIOMARKER_KEYS.issubset(entry.keys()), f"Missing keys in {entry}"


def test_every_biomarker_vitalog_id_in_ranges(ground_truth: dict) -> None:  # type: ignore[type-arg]
    for entry in ground_truth["biomarkers"]:
        assert entry["vitalog_id"] in BIOMARKER_RANGES


def test_collection_date_propagated_to_biomarkers(ground_truth: dict) -> None:  # type: ignore[type-arg]
    top_date = ground_truth["collection_date"]
    for entry in ground_truth["biomarkers"]:
        assert entry["collection_date"] == top_date


def test_lab_source_propagated_to_biomarkers(ground_truth: dict) -> None:  # type: ignore[type-arg]
    top_source = ground_truth["lab_source"]
    for entry in ground_truth["biomarkers"]:
        assert entry["lab_source"] == top_source


def test_custom_collection_date(tmp_path: Path) -> None:
    _, gt_path = generate_report(5, tmp_path, collection_date="2024-03-15")
    gt = json.loads(gt_path.read_text())
    assert gt["collection_date"] == "2024-03-15"
    for entry in gt["biomarkers"]:
        assert entry["collection_date"] == "2024-03-15"


def test_custom_lab_source(tmp_path: Path) -> None:
    _, gt_path = generate_report(6, tmp_path, lab_source="LabCorp")
    gt = json.loads(gt_path.read_text())
    assert gt["lab_source"] == "LabCorp"


def test_override_pins_biomarker_value(tmp_path: Path) -> None:
    _, gt_path = generate_report(7, tmp_path, overrides={"hba1c": "9.5"})
    gt = json.loads(gt_path.read_text())
    hba1c = next(b for b in gt["biomarkers"] if b["vitalog_id"] == "hba1c")
    assert hba1c["original_value"] == "9.5"


def test_pdf_file_created(tmp_path: Path) -> None:
    pdf_path, _ = generate_report(10, tmp_path)
    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 0


def test_ground_truth_file_created(tmp_path: Path) -> None:
    _, gt_path = generate_report(11, tmp_path)
    assert gt_path.exists()
    assert gt_path.stat().st_size > 0


def test_output_filenames(tmp_path: Path) -> None:
    pdf_path, gt_path = generate_report(42, tmp_path)
    assert pdf_path.name == "synthetic_000042.pdf"
    assert gt_path.name == "synthetic_000042.ground_truth.json"
