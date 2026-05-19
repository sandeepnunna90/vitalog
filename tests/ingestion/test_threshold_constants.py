"""C5 drift detector — fails if structurer.py constants diverge from calibration_report.md.

Run after every `make calibrate` to confirm the written constants match the report.
Skipped when calibration_report.md does not exist (pre-first-calibration).
"""

from __future__ import annotations

import re

import pytest

from src._paths import PROJECT_ROOT
from src.ingestion.structurer import THRESHOLD_AUTO_ACCEPT, THRESHOLD_REJECT

_REPORT_PATH = PROJECT_ROOT / "eval_corpus" / "calibration_report.md"

# Matches "THRESHOLD_AUTO_ACCEPT = 95.0" and "THRESHOLD_REJECT = 70.0" in the report
_TA_RE = re.compile(r"\*\*THRESHOLD_AUTO_ACCEPT\s*=\s*([\d.]+)\*\*")
_TR_RE = re.compile(r"\*\*THRESHOLD_REJECT\s*=\s*([\d.]+)\*\*")

# Matches only the failure-banner section header, not the description prose
_FAILED_RE = re.compile(r"^##.*CALIBRATION FAILED", re.MULTILINE)


def _parse_report() -> tuple[float, float] | None:
    """Return (ta, tr) from the chosen pair section, or None if CALIBRATION FAILED."""
    text = _REPORT_PATH.read_text()
    if _FAILED_RE.search(text):
        return None
    ta_match = _TA_RE.search(text)
    tr_match = _TR_RE.search(text)
    if not ta_match or not tr_match:
        raise ValueError(
            "calibration_report.md is present but chosen pair constants not found. "
            "Run `make calibrate` to regenerate."
        )
    return float(ta_match.group(1)), float(tr_match.group(1))


def test_constants_match_calibration_report() -> None:
    """AC5: constants in structurer.py must match the chosen pair in calibration_report.md."""
    if not _REPORT_PATH.exists():
        pytest.skip("calibration_report.md not yet generated — run `make calibrate` first")

    result = _parse_report()
    if result is None:
        # CALIBRATION FAILED path: report says fallback to (95.0, 70.0)
        expected_ta, expected_tr = 95.0, 70.0
    else:
        expected_ta, expected_tr = result

    assert THRESHOLD_AUTO_ACCEPT == expected_ta, (
        f"THRESHOLD_AUTO_ACCEPT={THRESHOLD_AUTO_ACCEPT} but calibration report says {expected_ta}. "
        "Run `make calibrate` to sync."
    )
    assert THRESHOLD_REJECT == expected_tr, (
        f"THRESHOLD_REJECT={THRESHOLD_REJECT} but calibration report says {expected_tr}. "
        "Run `make calibrate` to sync."
    )
