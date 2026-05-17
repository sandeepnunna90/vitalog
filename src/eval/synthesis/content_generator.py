"""Physiologically-plausible biomarker value sampler (deterministic from seed)."""

from __future__ import annotations

import random
from dataclasses import dataclass

# (low, high, decimal_places, display_unit)
BIOMARKER_RANGES: dict[str, tuple[float, float, int, str]] = {
    "hba1c": (4.0, 12.0, 1, "%"),
    "fasting_glucose": (70.0, 300.0, 0, "mg/dL"),
    "total_cholesterol": (120.0, 320.0, 0, "mg/dL"),
    "ldl_cholesterol": (50.0, 250.0, 0, "mg/dL"),
    "hdl_cholesterol": (25.0, 90.0, 0, "mg/dL"),
    "triglycerides": (50.0, 500.0, 0, "mg/dL"),
    "egfr": (15.0, 120.0, 0, "mL/min/1.73m2"),
    "creatinine": (0.5, 3.0, 2, "mg/dL"),
    "tsh": (0.1, 10.0, 2, "mIU/L"),
    "vitamin_d": (10.0, 80.0, 1, "ng/mL"),
    "hemoglobin": (10.0, 18.0, 1, "g/dL"),
    "wbc": (3.0, 14.0, 1, "10*3/uL"),
    "platelets": (100.0, 500.0, 0, "10*3/uL"),
    "sodium": (130.0, 150.0, 0, "mEq/L"),
    "potassium": (3.0, 6.0, 1, "mEq/L"),
    "bun": (5.0, 40.0, 0, "mg/dL"),
}

LAB_REFERENCE_RANGES: dict[str, str] = {
    "hba1c": "4.0-5.6%",
    "fasting_glucose": "70-99 mg/dL",
    "total_cholesterol": "<200 mg/dL",
    "ldl_cholesterol": "<100 mg/dL",
    "hdl_cholesterol": ">40 mg/dL",
    "triglycerides": "<150 mg/dL",
    "egfr": ">=60 mL/min/1.73m2",
    "creatinine": "0.74-1.35 mg/dL",
    "tsh": "0.5-4.5 mIU/L",
    "vitamin_d": "30-100 ng/mL",
    "hemoglobin": "13.5-17.5 g/dL",
    "wbc": "4.5-11.0 10*3/uL",
    "platelets": "150-400 10*3/uL",
    "sodium": "136-145 mEq/L",
    "potassium": "3.5-5.0 mEq/L",
    "bun": "7-20 mg/dL",
}

DISPLAY_NAMES: dict[str, str] = {
    "hba1c": "HbA1c",
    "fasting_glucose": "Glucose, Fasting",
    "total_cholesterol": "Cholesterol, Total",
    "ldl_cholesterol": "LDL Cholesterol",
    "hdl_cholesterol": "HDL Cholesterol",
    "triglycerides": "Triglycerides",
    "egfr": "eGFR",
    "creatinine": "Creatinine",
    "tsh": "TSH",
    "vitamin_d": "Vitamin D, 25-OH",
    "hemoglobin": "Hemoglobin",
    "wbc": "WBC",
    "platelets": "Platelets",
    "sodium": "Sodium",
    "potassium": "Potassium",
    "bun": "BUN",
}


@dataclass
class BiomarkerReading:
    vitalog_id: str
    original_name: str
    original_value: str
    original_unit: str
    original_range: str
    flag: str


def generate_readings(
    seed: int,
    overrides: dict[str, str] | None = None,
) -> list[BiomarkerReading]:
    """Return one reading per biomarker, sampled deterministically from seed.

    overrides maps vitalog_id → value string, used by H1 to pin specific values.
    """
    rng = random.Random(seed)
    readings: list[BiomarkerReading] = []
    for vid, (lo, hi, decimals, unit) in BIOMARKER_RANGES.items():
        if overrides and vid in overrides:
            value_str = overrides[vid]
        else:
            raw = rng.uniform(lo, hi)
            value = round(raw, decimals)
            value_str = f"{value:.{decimals}f}"
        readings.append(
            BiomarkerReading(
                vitalog_id=vid,
                original_name=DISPLAY_NAMES[vid],
                original_value=value_str,
                original_unit=unit,
                original_range=LAB_REFERENCE_RANGES[vid],
                flag="",
            )
        )
    return readings
