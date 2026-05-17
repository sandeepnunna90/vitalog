"""Unit tests for F1 — range overlay and band selection."""

from __future__ import annotations

from src.intelligence.range_overlay import _parse_range, select_bands
from src.reference_data import lookup_guideline


def _hba1c_guideline() -> tuple[dict[str, str], dict[str, str]]:
    g = lookup_guideline("hba1c")
    assert g is not None
    return g["guideline_ranges"], g["guideline_citations"]


# ── Range parsing ──────────────────────────────────────────────────────────────


def test_parse_upper_bound() -> None:
    lower, upper = _parse_range("<7.0%")
    assert lower is None
    assert upper == 7.0


def test_parse_range() -> None:
    lower, upper = _parse_range("5.7-6.4%")
    assert lower == 5.7
    assert upper == 6.4


def test_parse_lower_bound() -> None:
    lower, upper = _parse_range(">=6.5%")
    assert lower == 6.5
    assert upper is None


# ── Band selection ─────────────────────────────────────────────────────────────


def test_normal_band_always_present() -> None:
    ranges, citations = _hba1c_guideline()
    bands = select_bands(ranges, citations, [])
    labels = [b.label for b in bands]
    assert any("Normal" in label for label in labels)


def test_no_conditions_normal_only() -> None:
    ranges, citations = _hba1c_guideline()
    bands = select_bands(ranges, citations, [])
    assert len(bands) == 1


def test_t2d_gets_target_band() -> None:
    ranges, citations = _hba1c_guideline()
    bands = select_bands(ranges, citations, ["T2D"])
    assert len(bands) == 2
    labels = [b.label for b in bands]
    assert any("Target" in label for label in labels)


def test_t1d_also_gets_target_band() -> None:
    ranges, citations = _hba1c_guideline()
    bands = select_bands(ranges, citations, ["T1D"])
    assert len(bands) == 2
    labels = [b.label for b in bands]
    assert any("Target" in label for label in labels)


def test_citation_in_band() -> None:
    ranges, citations = _hba1c_guideline()
    bands = select_bands(ranges, citations, [])
    assert bands[0].citation is not None
    assert "ADA" in bands[0].citation or "American Diabetes" in bands[0].citation
