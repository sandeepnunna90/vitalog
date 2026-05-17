"""Physiological-range validation for converted biomarker values (E3)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.reference_data import load_taxonomy


@dataclass(frozen=True)
class RangeValidationResult:
    in_physiological_range: bool
    physiological_min: float
    physiological_max: float


def validate_physiological_range(vitalog_id: str, canonical_value: float) -> RangeValidationResult:
    """Check whether canonical_value falls within the physiological bounds for vitalog_id.

    Out-of-range values should be flagged for review (verified_by='pending_user')
    but are NOT discarded — the record must survive for audit purposes.

    Raises ValueError if vitalog_id is not found in the taxonomy.
    """
    taxonomy = load_taxonomy()
    entry: dict[str, Any] | None = next(
        (e for e in taxonomy if e["vitalog_id"] == vitalog_id), None
    )
    if entry is None:
        raise ValueError(f"vitalog_id {vitalog_id!r} not found in taxonomy")

    phys_min: float = entry["physiological_min"]
    phys_max: float = entry["physiological_max"]
    return RangeValidationResult(
        in_physiological_range=phys_min <= canonical_value <= phys_max,
        physiological_min=phys_min,
        physiological_max=phys_max,
    )
