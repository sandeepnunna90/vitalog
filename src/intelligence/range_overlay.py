"""Guideline range overlay — selects condition-specific bands from taxonomy data."""

from __future__ import annotations

import re
from typing import Any

from src.intelligence.trend_schemas import TrendBand

_CONDITION_PREFERRED_SUFFIXES: dict[str, list[str]] = {
    "T2D": ["target_diabetes", "target"],
    "T1D": ["target_diabetes", "target"],
    "prediabetes": ["prediabetes", "target"],
}


def _parse_range(raw: str) -> tuple[float | None, float | None]:
    s = raw.strip()
    m = re.match(r"^([0-9.]+)\s*[-–]\s*([0-9.]+)", s)
    if m:
        return float(m.group(1)), float(m.group(2))
    m = re.match(r"^<=?\s*([0-9.]+)", s)
    if m:
        return None, float(m.group(1))
    m = re.match(r"^>=?\s*([0-9.]+)", s)
    if m:
        return float(m.group(1)), None
    return None, None


def _make_label(key: str, raw_range: str) -> str:
    parts = key.split("_")
    authority = parts[0]
    description = " ".join(p.capitalize() for p in parts[1:])
    return f"{authority} {description}: {raw_range}"


def _match_authority(key: str, guideline_citations: dict[str, Any]) -> str | None:
    # Match longest citation key that is a prefix of the range key (handles "ACC_AHA" vs "ADA")
    for k in sorted(guideline_citations, key=len, reverse=True):
        if key.startswith(k + "_") or key == k:
            return k
    return None


def _make_band(key: str, raw_range: str, guideline_citations: dict[str, Any]) -> TrendBand:
    lower, upper = _parse_range(raw_range)
    authority = _match_authority(key, guideline_citations)
    citation = guideline_citations.get(authority) if authority else None
    return TrendBand(
        label=_make_label(key, raw_range),
        lower=lower,
        upper=upper,
        raw_range=raw_range,
        citation=citation,
    )


def _find_condition_target_key(
    guideline_ranges: dict[str, str],
    patient_conditions: list[str],
) -> str | None:
    for condition in patient_conditions:
        preferred_suffixes = _CONDITION_PREFERRED_SUFFIXES.get(condition, [])
        for suffix in preferred_suffixes:
            for key in guideline_ranges:
                if suffix in key.lower():
                    return key
    return None


def select_bands(
    guideline_ranges: dict[str, str],
    guideline_citations: dict[str, Any],
    patient_conditions: list[str],
) -> list[TrendBand]:
    bands: list[TrendBand] = []

    normal_key = next((k for k in guideline_ranges if "_normal" in k.lower()), None)
    if normal_key:
        bands.append(_make_band(normal_key, guideline_ranges[normal_key], guideline_citations))

    target_key = _find_condition_target_key(guideline_ranges, patient_conditions)
    if target_key and target_key != normal_key:
        bands.append(_make_band(target_key, guideline_ranges[target_key], guideline_citations))

    return bands
