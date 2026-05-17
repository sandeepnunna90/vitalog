"""Writes ground-truth JSON alongside a synthetic PDF."""

from __future__ import annotations

import json
from pathlib import Path

from src.eval.synthesis.content_generator import BiomarkerReading


def write_ground_truth(
    path: Path,
    readings: list[BiomarkerReading],
    collection_date: str,
    lab_source: str,
) -> None:
    payload = {
        "document_type": "lab_report",
        "lab_source": lab_source,
        "collection_date": collection_date,
        "patient_name": "TEST PATIENT",
        "patient_dob": "1970-01-01",
        "biomarkers": [
            {
                "vitalog_id": r.vitalog_id,
                "original_name": r.original_name,
                "original_value": r.original_value,
                "original_unit": r.original_unit,
                "original_range": r.original_range,
                "collection_date": collection_date,
                "lab_source": lab_source,
            }
            for r in readings
        ],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
