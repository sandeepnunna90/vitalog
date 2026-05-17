"""Adversarial banned-phrase suite for observation outputs (F2 AC2/AC5).

Tests Layer3 directly against observation-style prose — verifies that the B3
banned-phrase scanner catches clinical-advice phrases before they reach the caller.
"""

from __future__ import annotations

from typing import Any

import pytest

from src.gateway.errors import BannedPhraseViolation
from src.gateway.guardrails.layer3_deterministic import Layer3
from src.intelligence.observation_schemas import ObservationOutput


def _layer3() -> Layer3:
    return Layer3()


def _raw(text: str) -> dict[str, Any]:
    return {"text": text, "citations": []}


def _validate(text: str) -> ObservationOutput:
    return _layer3().validate_output(_raw(text), ObservationOutput)


# ── Banned phrases caught ─────────────────────────────────────────────────────


def test_you_should_caught() -> None:
    """'you should' is on the banned list — must raise BannedPhraseViolation."""
    with pytest.raises(BannedPhraseViolation):
        _validate("Your HbA1c is 6.8% — you should keep this up.")


def test_i_recommend_caught() -> None:
    with pytest.raises(BannedPhraseViolation):
        _validate("Your HbA1c is 6.8%. I recommend discussing this with your doctor.")


def test_diagnosed_with_caught() -> None:
    with pytest.raises(BannedPhraseViolation):
        _validate("Your HbA1c of 6.5% means you may be diagnosed with diabetes.")


def test_suggests_you_have_caught() -> None:
    with pytest.raises(BannedPhraseViolation):
        _validate("An HbA1c of 6.8% this suggests you have well-controlled diabetes.")


def test_you_are_at_risk_caught() -> None:
    with pytest.raises(BannedPhraseViolation):
        _validate("Based on this result, you are at risk of developing complications.")


# ── Clean factual observations pass ──────────────────────────────────────────


def test_clean_factual_observation_passes() -> None:
    """A plain factual observation with no banned phrases must pass Layer3."""
    text = (
        "Your HbA1c on 12 March 2026 was 6.8%, which is below the ADA target of "
        "less than 7.0% for adults with diabetes (ADA Standards of Care 2024). "
        "Your January 2026 result of 7.1% was above that target range."
    )
    result = _validate(text)
    assert result.text == text


def test_factual_with_comparison_passes() -> None:
    """Factual comparison language must pass (no advice, no inference)."""
    text = (
        "Your LDL cholesterol on 5 January 2026 was 3.4 mmol/L. "
        "The ACC/AHA guideline target for high cardiovascular risk is below 1.8 mmol/L "
        "(ACC/AHA 2019 Guideline on Primary Prevention)."
    )
    result = _validate(text)
    assert result.text == text
