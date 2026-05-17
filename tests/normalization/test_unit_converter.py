"""Unit tests for E3 — unit_converter."""

from __future__ import annotations

import pytest

from src.normalization.errors import UnitConversionError, UnitMissingError
from src.normalization.unit_converter import ConversionResult, convert

# ── IFCC formula (AC1) ────────────────────────────────────────────────────────


def test_hba1c_mmol_mol_to_percent() -> None:
    result = convert("hba1c", "48", "mmol/mol")
    # IFCC: 0.0915 * 48 + 2.15 = 4.392 + 2.15 = 6.542
    assert abs(result.canonical_value - 6.542) < 0.001
    assert result.canonical_unit == "%"
    assert result.range_qualifier == "eq"


def test_hba1c_ifcc_another_value() -> None:
    result = convert("hba1c", "53", "mmol/mol")
    # 0.0915 * 53 + 2.15 = 4.8495 + 2.15 = 6.9995
    assert abs(result.canonical_value - 6.9995) < 0.001


# ── Identity conversion (AC2) ─────────────────────────────────────────────────


def test_identity_when_already_canonical_unit() -> None:
    result = convert("hba1c", "6.5", "%")
    assert result.canonical_value == 6.5
    assert result.canonical_unit == "%"
    assert result.range_qualifier == "eq"


def test_identity_case_insensitive_unit_match() -> None:
    result = convert("fasting_glucose", "98", "MG/DL")
    assert result.canonical_value == 98.0
    assert result.canonical_unit == "mg/dL"


# ── Unknown unit raises UnitConversionError (AC3) ────────────────────────────


def test_unknown_unit_raises_unit_conversion_error() -> None:
    with pytest.raises(UnitConversionError) as exc_info:
        convert("hba1c", "6.5", "g/dL")
    assert exc_info.value.raw_unit == "g/dL"
    assert exc_info.value.vitalog_id == "hba1c"


def test_unknown_vitalog_id_raises_unit_conversion_error() -> None:
    with pytest.raises(UnitConversionError):
        convert("nonexistent_marker", "5.0", "mg/dL")


# ── Missing unit raises UnitMissingError (AC5) ─────────────────────────────────────


def test_none_unit_raises_unit_missing() -> None:
    with pytest.raises(UnitMissingError) as exc_info:
        convert("hba1c", "6.5", None)
    assert exc_info.value.vitalog_id == "hba1c"


def test_empty_unit_raises_unit_missing() -> None:
    with pytest.raises(UnitMissingError):
        convert("hba1c", "6.5", "")


def test_whitespace_unit_raises_unit_missing() -> None:
    with pytest.raises(UnitMissingError):
        convert("hba1c", "6.5", "   ")


# ── Qualifier parsing ─────────────────────────────────────────────────────────


def test_qualifier_lt_preserved() -> None:
    result = convert("hba1c", "<5.7", "%")
    assert result.canonical_value == 5.7
    assert result.range_qualifier == "lt"


def test_qualifier_gte_preserved() -> None:
    result = convert("hba1c", ">=6.5", "%")
    assert result.canonical_value == 6.5
    assert result.range_qualifier == "gte"


def test_qualifier_lte_preserved() -> None:
    result = convert("hba1c", "<=7.0", "%")
    assert result.canonical_value == 7.0
    assert result.range_qualifier == "lte"


def test_qualifier_gt_preserved() -> None:
    result = convert("hba1c", ">8.0", "%")
    assert result.canonical_value == 8.0
    assert result.range_qualifier == "gt"


# ── Linear formula (glucose, cholesterol) ────────────────────────────────────


def test_glucose_mmol_l_to_mg_dl() -> None:
    result = convert("fasting_glucose", "5.5", "mmol/L")
    # 5.5 * 18.0182 = 99.1001
    assert abs(result.canonical_value - 99.1) < 0.01
    assert result.canonical_unit == "mg/dL"


def test_cholesterol_mmol_l_to_mg_dl() -> None:
    result = convert("total_cholesterol", "5.18", "mmol/L")
    # 5.18 * 38.6659 = 200.29...
    assert abs(result.canonical_value - 200.3) < 0.1
    assert result.canonical_unit == "mg/dL"


def test_result_is_frozen_dataclass() -> None:
    result = convert("hba1c", "7.0", "%")
    assert isinstance(result, ConversionResult)
    with pytest.raises(Exception):
        result.canonical_value = 0.0  # type: ignore[misc]
