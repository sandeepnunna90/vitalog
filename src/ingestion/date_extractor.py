"""Document-level collection date extraction from lab report text."""

from __future__ import annotations

import logging
import re
from datetime import date

_log = logging.getLogger(__name__)

# Match common lab report collection-date labels. Capture the date token(s) that
# follow — either MM/DD/YYYY, ISO YYYY-MM-DD, or "Month DD YYYY" style.
# The label regex is case-insensitive; patterns are checked in priority order so
# more specific labels (e.g. "Date collected") win over shorter ones ("Collected").
_DATE_CAPTURE = (
    r"(\d{1,2}/\d{1,2}/\d{4}"  # MM/DD/YYYY  (LabCorp, Quest)
    r"|\d{4}-\d{2}-\d{2}"  # YYYY-MM-DD  (ISO)
    r"|[A-Za-z]+ +\d{1,2},? +\d{4}"  # Month DD YYYY  (some hospital systems)
    r")"
)

_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"Date\s+[Cc]ollected\s*:?\s*" + _DATE_CAPTURE, re.IGNORECASE),
    re.compile(r"Collection\s+Date\s*:?\s*" + _DATE_CAPTURE, re.IGNORECASE),
    re.compile(r"Date\s+of\s+Service\s*:?\s*" + _DATE_CAPTURE, re.IGNORECASE),
    re.compile(r"Specimen\s+Collected\s*:?\s*" + _DATE_CAPTURE, re.IGNORECASE),
    re.compile(r"Collected\s*:?\s*" + _DATE_CAPTURE, re.IGNORECASE),
    re.compile(r"Drawn\s*:?\s*" + _DATE_CAPTURE, re.IGNORECASE),
]


def extract_collection_date(text: str) -> date | None:
    """Return the first parseable collection date found in lab report text.

    Tries each label pattern in priority order. Returns None if no pattern
    matches or the matched string cannot be parsed as a date.
    """
    from dateutil import parser as du_parser
    from dateutil.parser import ParserError

    for pattern in _PATTERNS:
        m = pattern.search(text)
        if not m:
            continue
        raw = m.group(1).strip()
        # Fast path: ISO 8601
        try:
            return date.fromisoformat(raw)
        except ValueError:
            pass
        # General path: dateutil handles MM/DD/YYYY, Month DD YYYY, etc.
        # dayfirst=False enforces US month-first for ambiguous cases (06/05 → June 5).
        try:
            return du_parser.parse(raw, dayfirst=False).date()
        except (ParserError, ValueError, OverflowError):
            _log.debug("date_extractor: could not parse %r from label %r", raw, pattern.pattern)
            continue

    return None
