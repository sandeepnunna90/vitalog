"""Per-field composite confidence computation (architecture §5.1.1).

Composite = min(textract_confidence, llm_confidence, classification_confidence)
computed per candidate, not per document.

ClassificationResult.confidence is on a 0-1 scale; the other two are 0-100.
Scaling is done here so callers don't need to think about it.
"""

from __future__ import annotations


def compute_composite(
    textract_confidence: float,
    llm_confidence: float,
    classification_confidence: float,
) -> float:
    """Return the per-field composite confidence on a 0-100 scale.

    Args:
        textract_confidence: OCR floor from TextractResult (0-100 Textract-native scale).
        llm_confidence: LLM self-assessed confidence for this candidate (0-100).
        classification_confidence: Document classification confidence from D2 (0-1 scale).
    """
    return min(textract_confidence, llm_confidence, classification_confidence * 100.0)
