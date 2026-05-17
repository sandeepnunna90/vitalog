"""Numeric extractor for Mode B citation verification — regex + false-positive filter."""

from __future__ import annotations

import re
from dataclasses import dataclass

_MONTHS = {
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
    "jan",
    "feb",
    "mar",
    "apr",
    "jun",
    "jul",
    "aug",
    "sep",
    "oct",
    "nov",
    "dec",
}
_COUNT_WORDS = {"results", "records", "patients", "cases", "labs", "tests"}

# BP-style: 2-3 digit / 2-3 digit (right side must not be a 4-digit year)
_BP_RE = re.compile(r"(?<!\d)(\d{2,3})/(\d{2,3})(?!\d)")

# General numeric — decimal (with optional scientific exponent) or integer,
# followed by an optional adjacent unit token.
# Unit: single token starting with letter or %, may contain letters/digits/% and one embedded /
# (e.g. "mg/dL", "mmol/L", "IU/L"). Two-word units are intentionally not captured — all real
# clinical units are single tokens and the second-word group greedily picks up English verbs.
_NUM_RE = re.compile(
    r"(?<!\w)"
    r"((?:\d+\.\d*|\.\d+)(?:[eE][+-]?\d+)?|\d+(?:[eE][+-]?\d+)?)"
    r"(?:\s*((?:[a-zA-Z%][a-zA-Z\d%/]*)))?"
    r"(?![\d\w])"
)


@dataclass(frozen=True)
class ExtractedNumeric:
    value: float
    unit: str | None
    is_integer: bool  # True when original text had no decimal point


def parse(prose: str) -> list[ExtractedNumeric]:
    """Extract (value, unit, is_integer) tuples from prose, skipping false positives."""
    results: list[ExtractedNumeric] = []
    used_spans: set[int] = set()

    # Pass 1: BP-style slash ranges (must run before general pass to avoid double-extraction)
    for m in _BP_RE.finditer(prose):
        a, b = float(m.group(1)), float(m.group(2))
        if not (_is_year(a) or _is_year(b)):
            results.append(ExtractedNumeric(value=a, unit=None, is_integer=True))
            results.append(ExtractedNumeric(value=b, unit=None, is_integer=True))
        used_spans.update(range(m.start(), m.end()))

    # Pass 2: all other numerics
    for m in _NUM_RE.finditer(prose):
        if m.start() in used_spans:
            continue
        raw_num = m.group(1)
        raw_unit = m.group(2)
        v = float(raw_num)
        is_int = "." not in raw_num and "e" not in raw_num.lower()
        if _should_skip(prose, m, v):
            continue
        unit = raw_unit.strip() if raw_unit else None
        if unit is not None:
            if unit.lower() in _COUNT_WORDS:
                # The regex consumed the count word as the unit token (e.g. "9 results").
                # Skip the entire numeric — it's a record count, not a biomarker value.
                continue
            if not _is_valid_unit(unit):
                # English verbs/prepositions captured as the unit (e.g. "6.8 has improved").
                # Keep the numeric value but discard the spurious unit token.
                unit = None
        results.append(ExtractedNumeric(value=v, unit=unit, is_integer=is_int))

    return results


def _is_valid_unit(unit: str) -> bool:
    """Return True if `unit` looks like a real clinical unit rather than an English word.

    Real units always contain %, /, a digit, or an uppercase letter.
    Pure lowercase alphabetic tokens (e.g. "has", "was", "remained") are English words.
    """
    return "%" in unit or "/" in unit or any(c.isupper() or c.isdigit() for c in unit)


def _is_year(v: float) -> bool:
    return 1900.0 <= v <= 2099.0 and v == int(v)


def _should_skip(prose: str, m: re.Match[str], v: float) -> bool:
    if _is_year(v):
        return True
    # Preceded by a month name?
    pre = prose[: m.start()].rstrip()
    last_word = pre.split()[-1].rstrip(",.").lower() if pre.split() else ""
    if last_word in _MONTHS:
        return True
    # Followed by a count word or age suffix?
    post = prose[m.end() :]
    first_post = post.lstrip()
    first_word = first_post.split()[0].lower().strip(".,;") if first_post.split() else ""
    if first_word in _COUNT_WORDS:
        return True
    if first_post.startswith("-year") or first_post.startswith(" year"):
        return True
    return False
