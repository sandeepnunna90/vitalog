"""Unit tests for the Mode B numeric parser."""

from __future__ import annotations

from src.gateway.numeric_parser import ExtractedNumeric, parse


def _nums(prose: str) -> list[ExtractedNumeric]:
    return parse(prose)


def _vals(prose: str) -> list[float]:
    return [n.value for n in parse(prose)]


# ── Extraction happy paths ─────────────────────────────────────────────────────


def test_bare_decimal() -> None:
    nums = _nums("6.8")
    assert len(nums) == 1
    assert nums[0].value == 6.8
    assert nums[0].unit is None
    assert nums[0].is_integer is False


def test_decimal_with_percent() -> None:
    nums = _nums("6.8%")
    assert len(nums) == 1
    assert nums[0].value == 6.8
    assert nums[0].unit == "%"
    assert nums[0].is_integer is False


def test_integer_with_unit_space() -> None:
    nums = _nums("120 mg/dL")
    assert len(nums) == 1
    assert nums[0].value == 120.0
    assert nums[0].unit == "mg/dL"
    assert nums[0].is_integer is True


def test_bp_range_extracted_as_two_integers() -> None:
    nums = _nums("BP 120/80")
    values = [n.value for n in nums]
    assert 120.0 in values
    assert 80.0 in values
    assert all(n.is_integer for n in nums)
    assert all(n.unit is None for n in nums)


def test_parenthesized_value() -> None:
    """Value inside parentheses should be extracted normally."""
    nums = _nums("HbA1c (6.8%)")
    assert len(nums) == 1
    assert nums[0].value == 6.8
    assert nums[0].unit == "%"


def test_multiple_values_in_prose() -> None:
    prose = "Your HbA1c was 6.8%, down from 7.1% in January."
    vals = _vals(prose)
    assert 6.8 in vals
    assert 7.1 in vals


def test_decimal_no_unit_in_sentence() -> None:
    nums = _nums("LDL cholesterol measured at 3.4 mmol/L.")
    assert len(nums) == 1
    assert nums[0].value == 3.4
    assert nums[0].unit == "mmol/L"


# ── False-positive filters ─────────────────────────────────────────────────────


def test_year_not_extracted() -> None:
    assert _vals("in 2025") == []


def test_month_day_not_extracted() -> None:
    """Both the day (12) and year (2026) in 'March 12, 2026' must be filtered."""
    assert _vals("March 12, 2026") == []


def test_age_not_extracted() -> None:
    assert _vals("56-year-old patient") == []


def test_count_word_not_extracted() -> None:
    assert _vals("9 results") == []
    assert _vals("3 patients") == []


def test_bp_range_with_year_not_extracted() -> None:
    """If one side of A/B is a 4-digit year, skip the whole BP match."""
    # "12/2025" — right side has 4 digits so _BP_RE does not match; 2025 is filtered as a year.
    # 12 is extracted as a bare integer (no preceding month name to filter it).
    nums = _nums("recorded on 12/2025")
    values = [n.value for n in nums]
    assert 2025.0 not in values
    assert values == [12.0]
