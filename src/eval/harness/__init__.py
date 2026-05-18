"""Extraction accuracy harness (C3).

Runs the full ingestion pipeline (D1–D6) against the eval corpus and emits
per-field precision/recall/F1 against ground truth JSON.
"""

from src.eval.harness.aggregator import AggregateReport, DocResult, FieldMetrics, aggregate
from src.eval.harness.comparator import (
    BiomarkerMatch,
    DocComparison,
    FieldResult,
    compare_doc,
)
from src.eval.harness.reporter import append_history, write_report
from src.eval.harness.runner import HarnessRunner, Pipeline

__all__ = [
    "AggregateReport",
    "BiomarkerMatch",
    "DocComparison",
    "DocResult",
    "FieldMetrics",
    "FieldResult",
    "HarnessRunner",
    "Pipeline",
    "aggregate",
    "append_history",
    "compare_doc",
    "write_report",
]
