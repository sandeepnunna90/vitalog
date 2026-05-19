"""C5 calibration grid search — sweeps THRESHOLD_AUTO_ACCEPT × THRESHOLD_REJECT.

Definitions (documented in calibration_report.md):
  auto-accept precision = of records routed to auto-accept, fraction with correct value
  auto-accept recall    = of all correct records in corpus, fraction that landed in auto-accept
  review precision      = of records routed to review, fraction with correct value

"Correct" for a matched candidate: value field match within ±0.5% tolerance (same rule as Mode B).
Name correctness is implied by the fuzzy-match precondition (score >= 90.0).
"""

from __future__ import annotations

from dataclasses import dataclass

from src.eval.harness.aggregator import DocResult
from src.eval.harness.comparator import BiomarkerMatch

THRESHOLDS_AUTO_ACCEPT: list[float] = [90.0, 92.0, 95.0, 97.0, 99.0]
THRESHOLDS_REJECT: list[float] = [60.0, 65.0, 70.0, 75.0, 80.0]

AA_RECALL_MIN: float = 0.95
REVIEW_PRECISION_MIN: float = 0.80


@dataclass
class GridCell:
    threshold_auto_accept: float
    threshold_reject: float
    aa_precision: float
    aa_recall: float
    review_precision: float
    aa_total: int
    review_total: int
    reject_total: int


def run_grid(doc_results: list[DocResult]) -> list[GridCell]:
    """Sweep all 25 threshold pairs and return one GridCell per pair."""
    cells: list[GridCell] = []
    for ta in THRESHOLDS_AUTO_ACCEPT:
        for tr in THRESHOLDS_REJECT:
            cells.append(_eval_pair(doc_results, ta, tr))
    return cells


def pick_best(cells: list[GridCell]) -> GridCell | None:
    """Return the qualifying cell with the highest aa_precision, or None if none qualify.

    Selection rule: aa_recall >= AA_RECALL_MIN AND review_precision >= REVIEW_PRECISION_MIN,
    then maximise aa_precision.
    """
    qualifying = [
        c
        for c in cells
        if c.aa_recall >= AA_RECALL_MIN and c.review_precision >= REVIEW_PRECISION_MIN
    ]
    if not qualifying:
        return None
    return max(qualifying, key=lambda c: c.aa_precision)


def _eval_pair(doc_results: list[DocResult], ta: float, tr: float) -> GridCell:
    aa_correct = 0
    aa_incorrect = 0
    review_correct = 0
    review_incorrect = 0
    reject_count = 0
    all_correct = 0  # denominator for aa_recall

    for dr in doc_results:
        cmp = dr.comparison

        for bm in cmp.biomarker_matches:
            if bm.matched:
                value_correct = _is_value_correct(bm)
                composite = bm.matched_composite_confidence

                if composite is None:
                    # Dry-run path: no real composite, use band as proxy
                    composite = _band_to_proxy_composite(bm.matched_band)

                if composite >= ta:
                    if value_correct:
                        aa_correct += 1
                    else:
                        aa_incorrect += 1
                elif composite >= tr:
                    if value_correct:
                        review_correct += 1
                    else:
                        review_incorrect += 1
                else:
                    reject_count += 1

                if value_correct:
                    all_correct += 1
            else:
                # Unmatched GT — always FN; never correct
                pass

        # Unmatched extracted candidates → FP in whichever band they fall into
        for comp in cmp.unmatched_extracted_composites:
            if comp >= ta:
                aa_incorrect += 1
            elif comp >= tr:
                review_incorrect += 1
            else:
                reject_count += 1

    aa_total = aa_correct + aa_incorrect
    review_total = review_correct + review_incorrect

    aa_precision = aa_correct / aa_total if aa_total > 0 else 1.0
    aa_recall = aa_correct / all_correct if all_correct > 0 else 1.0
    review_precision = review_correct / review_total if review_total > 0 else 1.0

    return GridCell(
        threshold_auto_accept=ta,
        threshold_reject=tr,
        aa_precision=aa_precision,
        aa_recall=aa_recall,
        review_precision=review_precision,
        aa_total=aa_total,
        review_total=review_total,
        reject_total=reject_count,
    )


def _is_value_correct(bm: BiomarkerMatch) -> bool:
    for fr in bm.fields:
        if fr.field == "value":
            return fr.match
    return False


def _band_to_proxy_composite(band: str | None) -> float:
    """Map band string to a representative composite for dry-run mode."""
    if band == "auto_accept":
        return 97.0
    if band == "review":
        return 82.0
    return 50.0
