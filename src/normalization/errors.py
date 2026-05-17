"""Normalization-specific exceptions."""

from __future__ import annotations


class UnitConversionError(Exception):
    """Raised when no conversion rule exists for the raw unit → canonical unit."""

    def __init__(self, vitalog_id: str, raw_unit: str, detail: str = "") -> None:
        self.vitalog_id = vitalog_id
        self.raw_unit = raw_unit
        suffix = f": {detail}" if detail else ""
        super().__init__(
            f"No conversion rule for {raw_unit!r} → canonical unit of {vitalog_id!r}{suffix}"
        )


class UnitMissingError(Exception):
    """Raised when a biomarker candidate has no unit string."""

    def __init__(self, vitalog_id: str) -> None:
        self.vitalog_id = vitalog_id
        super().__init__(f"Unit missing for {vitalog_id!r}")
