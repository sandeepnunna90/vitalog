"""Shared numeric constants for the normalization pipeline."""

# 0.5% tolerance — used by duplicate detection (E4) and Mode B citation verifier (B5)
MODE_B_NUMERIC_TOLERANCE: float = 0.005


def within_tolerance(cited: float, stored: float, tolerance: float) -> bool:
    """Return True if cited is within ±tolerance % of stored.

    Zero-stored case requires exact match (zero glucose / potassium is not
    a rounding error; treat as a data integrity flag rather than a boundary).
    Same pattern used in citation_verifier_mode_a and eval/harness/comparator.
    """
    if stored == 0.0:
        return cited == 0.0
    return abs(cited - stored) / abs(stored) <= tolerance
