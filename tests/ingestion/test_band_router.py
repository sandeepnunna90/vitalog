"""Unit tests for band_router.assign_band()."""

from __future__ import annotations

from src.ingestion.band_router import assign_band
from src.ingestion.structurer import THRESHOLD_AUTO_ACCEPT, THRESHOLD_REJECT
from src.ingestion.structurer_schemas import Band


def test_exactly_at_auto_accept_threshold() -> None:
    """95.0 with defaults → AUTO_ACCEPT (condition is >=)."""
    assert (
        assign_band(THRESHOLD_AUTO_ACCEPT, THRESHOLD_AUTO_ACCEPT, THRESHOLD_REJECT)
        == Band.AUTO_ACCEPT
    )


def test_just_above_auto_accept() -> None:
    assert assign_band(95.1, THRESHOLD_AUTO_ACCEPT, THRESHOLD_REJECT) == Band.AUTO_ACCEPT


def test_hundred_is_auto_accept() -> None:
    assert assign_band(100.0, THRESHOLD_AUTO_ACCEPT, THRESHOLD_REJECT) == Band.AUTO_ACCEPT


def test_just_below_auto_accept_is_review() -> None:
    assert assign_band(94.9, THRESHOLD_AUTO_ACCEPT, THRESHOLD_REJECT) == Band.REVIEW


def test_midpoint_is_review() -> None:
    mid = (THRESHOLD_AUTO_ACCEPT + THRESHOLD_REJECT) / 2
    assert assign_band(mid, THRESHOLD_AUTO_ACCEPT, THRESHOLD_REJECT) == Band.REVIEW


def test_exactly_at_reject_threshold_is_review() -> None:
    """70.0 → REVIEW, not REJECT (condition is >=)."""
    assert assign_band(THRESHOLD_REJECT, THRESHOLD_AUTO_ACCEPT, THRESHOLD_REJECT) == Band.REVIEW


def test_just_below_reject_threshold_is_reject() -> None:
    assert assign_band(69.9, THRESHOLD_AUTO_ACCEPT, THRESHOLD_REJECT) == Band.REJECT


def test_zero_is_reject() -> None:
    assert assign_band(0.0, THRESHOLD_AUTO_ACCEPT, THRESHOLD_REJECT) == Band.REJECT


def test_custom_thresholds_respected() -> None:
    """Custom thresholds override the defaults — band_router is threshold-agnostic."""
    assert assign_band(80.0, threshold_auto_accept=90.0, threshold_reject=60.0) == Band.REVIEW
    assert assign_band(59.9, threshold_auto_accept=90.0, threshold_reject=60.0) == Band.REJECT
    assert assign_band(90.0, threshold_auto_accept=90.0, threshold_reject=60.0) == Band.AUTO_ACCEPT
