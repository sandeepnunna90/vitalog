"""Unit tests for E3 — range_validator."""

from __future__ import annotations

import pytest

from src.normalization.range_validator import RangeValidationResult, validate_physiological_range

# ── HbA1c physiological range [3.0, 18.0] % ─────────────────────────────────


def test_in_range_returns_true() -> None:
    result = validate_physiological_range("hba1c", 6.5)
    assert result.in_physiological_range is True
    assert result.physiological_min == 3.0
    assert result.physiological_max == 18.0


def test_below_min_returns_false() -> None:
    result = validate_physiological_range("hba1c", 1.0)
    assert result.in_physiological_range is False


def test_above_max_returns_false() -> None:
    result = validate_physiological_range("hba1c", 25.0)
    assert result.in_physiological_range is False


def test_boundary_min_included() -> None:
    result = validate_physiological_range("hba1c", 3.0)
    assert result.in_physiological_range is True


def test_boundary_max_included() -> None:
    result = validate_physiological_range("hba1c", 18.0)
    assert result.in_physiological_range is True


# ── Other biomarkers ──────────────────────────────────────────────────────────


def test_glucose_in_range() -> None:
    result = validate_physiological_range("fasting_glucose", 98.0)
    assert result.in_physiological_range is True


def test_glucose_extreme_high_out_of_range() -> None:
    result = validate_physiological_range("fasting_glucose", 700.0)
    assert result.in_physiological_range is False


def test_result_is_frozen_dataclass() -> None:
    result = validate_physiological_range("hba1c", 6.5)
    assert isinstance(result, RangeValidationResult)
    with pytest.raises(Exception):
        result.in_physiological_range = False  # type: ignore[misc]


# ── Error handling ────────────────────────────────────────────────────────────


def test_unknown_vitalog_id_raises_value_error() -> None:
    with pytest.raises(ValueError, match="not found in taxonomy"):
        validate_physiological_range("nonexistent_marker", 5.0)
