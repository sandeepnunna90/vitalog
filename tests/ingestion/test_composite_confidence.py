"""Unit tests for composite_confidence.compute_composite()."""

from __future__ import annotations

from src.ingestion.composite_confidence import compute_composite


def test_minimum_of_three_signals() -> None:
    """Returns the smallest of the three signals (after scaling classification)."""
    result = compute_composite(
        textract_confidence=90.0, llm_confidence=85.0, classification_confidence=0.95
    )
    assert result == 85.0


def test_textract_is_lowest() -> None:
    result = compute_composite(
        textract_confidence=50.0, llm_confidence=90.0, classification_confidence=0.95
    )
    assert result == 50.0


def test_llm_is_lowest() -> None:
    result = compute_composite(
        textract_confidence=90.0, llm_confidence=40.0, classification_confidence=0.95
    )
    assert result == 40.0


def test_classification_is_lowest() -> None:
    """classification_confidence=0.5 scales to 50.0 — beats the other two signals."""
    result = compute_composite(
        textract_confidence=90.0, llm_confidence=80.0, classification_confidence=0.5
    )
    assert result == 50.0


def test_classification_confidence_scaled_from_01() -> None:
    """classification_confidence is on 0-1; 0.8 must become 80.0 before comparison."""
    result = compute_composite(
        textract_confidence=85.0, llm_confidence=90.0, classification_confidence=0.8
    )
    assert result == 80.0


def test_all_equal_signals() -> None:
    result = compute_composite(
        textract_confidence=90.0, llm_confidence=90.0, classification_confidence=0.9
    )
    assert result == 90.0


def test_all_perfect_signals() -> None:
    result = compute_composite(
        textract_confidence=100.0, llm_confidence=100.0, classification_confidence=1.0
    )
    assert result == 100.0


def test_all_zero_signals() -> None:
    result = compute_composite(
        textract_confidence=0.0, llm_confidence=0.0, classification_confidence=0.0
    )
    assert result == 0.0


def test_classification_zero_dominates() -> None:
    """classification_confidence=0.0 → composite must be 0.0 regardless of others."""
    result = compute_composite(
        textract_confidence=99.0, llm_confidence=99.0, classification_confidence=0.0
    )
    assert result == 0.0
