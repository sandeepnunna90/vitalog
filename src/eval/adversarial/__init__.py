"""Adversarial prompt suite grader (C4).

Classifies LLM output as refusal / safe_redirect / clinical_advice using
the L3 banned-phrase scanner plus deterministic regex patterns and an
optional tiebreaker LLM call.
"""

from src.eval.adversarial.grader import (
    AdversarialGrader,
    Grade,
    GradeResult,
    GraderOutput,
    PromptSpec,
    load_prompt_spec,
)

__all__ = [
    "AdversarialGrader",
    "Grade",
    "GradeResult",
    "GraderOutput",
    "PromptSpec",
    "load_prompt_spec",
]
