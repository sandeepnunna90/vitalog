"""3-band routing: auto_accept / review / reject (architecture §5.1).

Thresholds are passed in from structurer.py constants so that C5 calibration
can adjust them without touching this module.
"""

from __future__ import annotations

from src.ingestion.structurer_schemas import Band


def assign_band(
    composite_confidence: float,
    threshold_auto_accept: float,
    threshold_reject: float,
) -> Band:
    """Map a composite confidence score to an ingestion band.

    Bands (both boundaries are inclusive at the lower end):
      auto_accept  ≥ threshold_auto_accept
      review       threshold_reject ≤ c < threshold_auto_accept
      reject       < threshold_reject
    """
    if composite_confidence >= threshold_auto_accept:
        return Band.AUTO_ACCEPT
    elif composite_confidence >= threshold_reject:
        return Band.REVIEW
    else:
        return Band.REJECT
