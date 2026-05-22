"""Deterministic unit conversion for biomarker candidates (E3, P4 — zero LLM calls)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from src.normalization.errors import UnitConversionError, UnitMissingError
from src.reference_data import load_taxonomy

# Matches optional qualifier prefix then a decimal number.
_QUALIFIER_RE = re.compile(r"^([<>]=?)\s*([\d.]+)")
_NUMERIC_RE = re.compile(r"^([\d.]+)")

_QUALIFIER_MAP = {"<": "lt", "<=": "lte", ">": "gt", ">=": "gte"}

# IFCC→NGSP formula constants (HbA1c mmol/mol → %)
_IFCC_FACTOR = 0.0915
_IFCC_OFFSET = 2.15


@dataclass(frozen=True)
class ConversionResult:
    canonical_value: float
    canonical_unit: str
    range_qualifier: str  # "eq" | "lt" | "lte" | "gt" | "gte"


def convert(vitalog_id: str, raw_value_str: str, raw_unit: str | None) -> ConversionResult:
    """Convert raw_value_str + raw_unit to the canonical unit for vitalog_id.

    Raises UnitMissingError when raw_unit is absent.
    Raises UnitConversionError when no rule covers the raw unit.
    Raises ValueError when raw_value_str cannot be parsed as a number.
    """
    if not raw_unit or not raw_unit.strip():
        raise UnitMissingError(vitalog_id)

    taxonomy = load_taxonomy()
    entry = _find_entry(taxonomy, vitalog_id)
    if entry is None:
        raise UnitConversionError(vitalog_id, raw_unit.strip(), "vitalog_id not in taxonomy")

    canonical_unit: str = entry["ucum_unit"]
    raw_unit_norm = raw_unit.strip()

    raw_numeric, qualifier = _parse_value(raw_value_str)

    if _units_equal(raw_unit_norm, canonical_unit):
        return ConversionResult(
            canonical_value=raw_numeric,
            canonical_unit=canonical_unit,
            range_qualifier=qualifier,
        )

    rule = _find_rule(entry.get("unit_conversions", []), raw_unit_norm)
    if rule is None:
        raise UnitConversionError(vitalog_id, raw_unit_norm)

    converted = _apply_formula(rule, raw_numeric)
    return ConversionResult(
        canonical_value=converted,
        canonical_unit=canonical_unit,
        range_qualifier=qualifier,
    )


# ── helpers ───────────────────────────────────────────────────────────────────


def _find_entry(taxonomy: list[dict[str, Any]], vitalog_id: str) -> dict[str, Any] | None:
    return next((e for e in taxonomy if e["vitalog_id"] == vitalog_id), None)


_XEXP_RE = re.compile(r"x10e(\d+)", re.IGNORECASE)


def _normalize_unit(u: str) -> str:
    """Collapse common notation variants to a single form for comparison.

    x10E3/uL → 10*3/uL (LabCorp scientific-notation style → UCUM multiply style)
    """
    return _XEXP_RE.sub(lambda m: f"10*{m.group(1)}", u.strip().lower())


def _units_equal(a: str, b: str) -> bool:
    # Case-fold intentionally: UCUM is case-significant in strict mode, but real-world
    # lab reports routinely emit "MG/DL", "Mg/dL", etc. Pragmatic relaxation for capstone.
    return _normalize_unit(a) == _normalize_unit(b)


def _find_rule(conversions: list[dict[str, Any]], raw_unit_norm: str) -> dict[str, Any] | None:
    return next(
        (r for r in conversions if _units_equal(r["from_unit"], raw_unit_norm)),
        None,
    )


def _parse_value(raw: str) -> tuple[float, str]:
    """Return (numeric_value, qualifier) from a raw value string.

    Handles '<5.7', '>=6.5', plain '6.8', and '6.8 %' (strips trailing text).
    """
    raw = raw.strip()
    m = _QUALIFIER_RE.match(raw)
    if m:
        return float(m.group(2)), _QUALIFIER_MAP[m.group(1)]
    m = _NUMERIC_RE.match(raw)
    if m:
        return float(m.group(1)), "eq"
    raise ValueError(f"Cannot parse numeric value from {raw!r}")


def _apply_formula(rule: dict[str, Any], raw: float) -> float:
    formula: str = rule["formula"]
    if formula == "linear":
        return float(rule["factor"]) * raw
    if formula == "ifcc_to_ngsp":
        return _IFCC_FACTOR * raw + _IFCC_OFFSET
    raise ValueError(f"Unknown conversion formula {formula!r}")
