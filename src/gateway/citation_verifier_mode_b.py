"""Mode B citation verifier — parse numerics from prose, match against retrieval set.

Zero LLM calls. Caller supplies the retrieval set; this module does no I/O.
"""

from __future__ import annotations

import logging
import uuid

from src.gateway.errors import UnitMismatchError, UnmatchedNumericError
from src.gateway.numeric_parser import ExtractedNumeric, parse
from src.persistence.models import BiomarkerRecordRow

MODE_B_NUMERIC_TOLERANCE = 0.005  # ±0.5% per §7.2.1

_eval_log = logging.getLogger("verification.eval")


def verify(
    prose: str,
    retrieval_set: dict[uuid.UUID, BiomarkerRecordRow],
) -> None:
    """Verify all numerics extracted from prose against the retrieval set.

    Raises UnmatchedNumericError or UnitMismatchError on first failure.
    Returns None on success. Zero I/O — pure deterministic.
    AC6 retry-on-failure (retry once with stricter prompt, then safe refusal) is the caller's
    responsibility (F2 Observation Generator, F3 NLQ Handler).
    """
    for numeric in parse(prose):
        _verify_one(numeric, retrieval_set)


def _verify_one(
    numeric: ExtractedNumeric,
    retrieval_set: dict[uuid.UUID, BiomarkerRecordRow],
) -> None:
    value_matches = [
        (rid, rec) for rid, rec in retrieval_set.items() if _value_matches(numeric, rec)
    ]

    if not value_matches:
        _eval_log.info(
            "Mode B: unmatched numeric",
            extra={"value": numeric.value, "unit": numeric.unit, "result": "unmatched"},
        )
        raise UnmatchedNumericError(numeric.value, numeric.unit)

    if numeric.unit is not None:
        unit_ok = any(_unit_matches(numeric.unit, rec) for _, rec in value_matches)
        if not unit_ok:
            _eval_log.info(
                "Mode B: unit mismatch",
                extra={"value": numeric.value, "unit": numeric.unit, "result": "unit_mismatch"},
            )
            raise UnitMismatchError(value=numeric.value, cited_unit=numeric.unit)

    matched_rid = value_matches[0][0]
    _eval_log.info(
        "Mode B: matched",
        extra={
            "value": numeric.value,
            "matched_record_id": str(matched_rid),
            "result": "matched",
        },
    )


def _value_matches(numeric: ExtractedNumeric, record: BiomarkerRecordRow) -> bool:
    if numeric.is_integer:
        # AC4: exact match required for integers
        canon_ok = record.canonical_value is not None and record.canonical_value == numeric.value
        return canon_ok or _original_exact(numeric.value, record)
    else:
        # AC5: ±0.5% tolerance against canonical_value OR original_value
        return _within_tol(numeric.value, record.canonical_value) or _within_tol_orig(
            numeric.value, record
        )


def _within_tol(cited: float, stored: float | None) -> bool:
    if stored is None:
        return False
    if stored == 0.0:
        return cited == 0.0
    return abs(cited - stored) / abs(stored) <= MODE_B_NUMERIC_TOLERANCE


def _within_tol_orig(cited: float, record: BiomarkerRecordRow) -> bool:
    # Qualifier-prefixed strings (e.g. "<5.7", ">100") raise ValueError → return False.
    # The LLM must cite the bare numeric value, not the qualifier form.
    try:
        return _within_tol(cited, float(record.original_value))
    except (ValueError, TypeError):
        return False


def _original_exact(cited: float, record: BiomarkerRecordRow) -> bool:
    # Same qualifier caveat as _within_tol_orig: "<5" → float() raises → False.
    try:
        return float(record.original_value) == cited
    except (ValueError, TypeError):
        return False


def _unit_matches(cited_unit: str, record: BiomarkerRecordRow) -> bool:
    return cited_unit == record.canonical_unit or cited_unit == record.original_unit
