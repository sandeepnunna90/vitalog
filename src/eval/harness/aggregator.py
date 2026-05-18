"""Precision / recall / F1 aggregation over per-document DocComparison results."""

from __future__ import annotations

from dataclasses import dataclass

from src.eval.harness.comparator import FIELDS, DocComparison


@dataclass
class FieldMetrics:
    field: str
    tp: int = 0
    fp: int = 0
    fn: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0


@dataclass
class DocResult:
    filename: str
    split: str
    vendor: str
    expected_classification: str
    actual_classification: str
    classification_correct: bool
    comparison: DocComparison


@dataclass
class AggregateReport:
    run_id: str
    total_docs: int
    overall: list[FieldMetrics]  # across all docs
    by_split: dict[str, list[FieldMetrics]]  # split → per-field metrics
    by_band: dict[str, list[FieldMetrics]]  # band → per-field metrics (matched pairs only)
    doc_results: list[DocResult]


def aggregate(doc_results: list[DocResult], run_id: str) -> AggregateReport:
    """Compute precision/recall/F1 per field across all docs, by split, and by band."""
    overall = _field_metrics_from_results(doc_results)

    by_split: dict[str, list[FieldMetrics]] = {}
    for split in sorted({r.split for r in doc_results}):
        subset = [r for r in doc_results if r.split == split]
        by_split[split] = _field_metrics_from_results(subset)

    all_bands: set[str] = set()
    for r in doc_results:
        all_bands.update(r.comparison.band_distribution.keys())
    by_band: dict[str, list[FieldMetrics]] = {}
    for band in sorted(all_bands):
        by_band[band] = _field_metrics_from_band(doc_results, band)

    return AggregateReport(
        run_id=run_id,
        total_docs=len(doc_results),
        overall=overall,
        by_split=by_split,
        by_band=by_band,
        doc_results=doc_results,
    )


def _field_metrics_from_results(doc_results: list[DocResult]) -> list[FieldMetrics]:
    """TP/FP/FN per field across all DocResults.

    For each field:
      - Matched GT biomarker + field correct  → TP
      - Matched GT biomarker + field wrong    → FP + FN (wrong prediction + missed correct)
      - Unmatched GT biomarker (not extracted)→ FN for every field
      - Extra extracted (no GT match)         → FP for every field
    """
    counts: dict[str, dict[str, int]] = {f: {"tp": 0, "fp": 0, "fn": 0} for f in FIELDS}

    for result in doc_results:
        cmp = result.comparison
        for bm in cmp.biomarker_matches:
            if bm.matched:
                for fr in bm.fields:
                    if fr.match:
                        counts[fr.field]["tp"] += 1
                    else:
                        counts[fr.field]["fp"] += 1
                        counts[fr.field]["fn"] += 1
            else:
                for f in FIELDS:
                    counts[f]["fn"] += 1

        for f in FIELDS:
            counts[f]["fp"] += cmp.extra_extracted

    metrics: list[FieldMetrics] = []
    for f in FIELDS:
        tp = counts[f]["tp"]
        fp = counts[f]["fp"]
        fn = counts[f]["fn"]
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        metrics.append(
            FieldMetrics(field=f, tp=tp, fp=fp, fn=fn, precision=precision, recall=recall, f1=f1)
        )
    return metrics


def _field_metrics_from_band(doc_results: list[DocResult], band: str) -> list[FieldMetrics]:
    """Per-field metrics considering only matched pairs whose extracted candidate is in `band`.

    FN from unmatched GT and FP from extra extracted are not included here — by-band metrics
    reflect extraction precision within confirmed-band candidates.
    """
    counts: dict[str, dict[str, int]] = {f: {"tp": 0, "fp": 0, "fn": 0} for f in FIELDS}

    for result in doc_results:
        for bm in result.comparison.biomarker_matches:
            if not bm.matched or bm.matched_band != band:
                continue
            for fr in bm.fields:
                if fr.match:
                    counts[fr.field]["tp"] += 1
                else:
                    counts[fr.field]["fp"] += 1
                    counts[fr.field]["fn"] += 1

    metrics: list[FieldMetrics] = []
    for f in FIELDS:
        tp = counts[f]["tp"]
        fp = counts[f]["fp"]
        fn = counts[f]["fn"]
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        metrics.append(
            FieldMetrics(field=f, tp=tp, fp=fp, fn=fn, precision=precision, recall=recall, f1=f1)
        )
    return metrics
