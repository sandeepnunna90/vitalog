"""Harness runner — loads the eval corpus, dispatches pipeline or GT self-comparison.

In dry-run mode no API calls are made: GT biomarkers are converted to mock
BiomarkerCandidate objects (GT values verbatim) and compared against themselves,
which produces ~100% F1 and validates the harness scaffolding end-to-end.

In live mode a fully-initialised Pipeline must be provided; the runner invokes
D1 → D2 → D4 → D5 → D6 per document and captures BiomarkerCandidates.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.eval.harness.aggregator import DocResult
from src.eval.harness.comparator import compare_doc
from src.ingestion.classification_schemas import Category
from src.ingestion.structurer_schemas import Band, BiomarkerCandidate


@dataclass
class Pipeline:
    """Fully-initialised ingestion pipeline components for a live harness run."""

    validator: Any  # UploadValidator — Any to avoid circular dep in tests
    classifier: Any  # DocumentClassifier
    textract: Any  # TextractAdapter
    fallback: Any  # TextractFallbackAdapter
    structurer: Any  # Structurer


class HarnessRunner:
    def __init__(
        self,
        corpus_root: Path,
        *,
        dry_run: bool = False,
        pipeline: Pipeline | None = None,
    ) -> None:
        if not dry_run and pipeline is None:
            raise ValueError("pipeline must be provided when dry_run=False")
        self._corpus_root = corpus_root
        self._dry_run = dry_run
        self._pipeline = pipeline

    def run_all(self) -> list[DocResult]:
        manifest_path = self._corpus_root / "manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError(
                f"manifest.json not found at {manifest_path}. Run scripts/build_manifest.py first."
            )
        manifest: dict[str, Any] = json.loads(manifest_path.read_text())
        entries: list[dict[str, Any]] = manifest.get("documents", [])
        return [self._run_one(entry) for entry in entries]

    def _run_one(self, entry: dict[str, Any]) -> DocResult:
        split: str = entry["split"]
        filename: str = entry["filename"]
        vendor: str = entry.get("vendor", "unknown")
        expected_classification: str = entry.get("expected_classification", "lab_report")

        pdf_path = self._corpus_root / split / filename
        gt_path = pdf_path.with_suffix("").with_suffix(".ground_truth.json")

        gt: dict[str, Any] = json.loads(gt_path.read_text()) if gt_path.exists() else {}
        gt_biomarkers: list[dict[str, str]] = gt.get("biomarkers", [])

        if self._dry_run:
            candidates = _gt_to_candidates(gt_biomarkers)
            actual_classification = expected_classification
        else:
            candidates, actual_classification = self._run_pipeline(pdf_path, entry)

        comparison = compare_doc(candidates, gt_biomarkers)
        return DocResult(
            filename=filename,
            split=split,
            vendor=vendor,
            expected_classification=expected_classification,
            actual_classification=actual_classification,
            classification_correct=(actual_classification == expected_classification),
            comparison=comparison,
        )

    def _run_pipeline(
        self, pdf_path: Path, entry: dict[str, Any]
    ) -> tuple[list[BiomarkerCandidate], str]:
        """Run D1 → D2 → D4 → D5 → D6 and return (candidates, classification_category_value)."""
        assert self._pipeline is not None  # guaranteed by __init__
        p = self._pipeline

        pdf_bytes = pdf_path.read_bytes()
        upload = p.validator.validate(pdf_bytes, pdf_path.name)
        classification = p.classifier.classify(upload)

        actual_category: str = classification.category.value
        if classification.category != Category.LAB_REPORT:
            return [], actual_category

        doc_id = uuid.uuid4()
        textract_result = p.textract.extract(upload, doc_id)
        textract_result = p.fallback.extract(upload, doc_id, textract_result)
        structurer_result = p.structurer.structure(
            textract_result, doc_id, classification.confidence
        )
        return structurer_result.candidates, actual_category


def _gt_to_candidates(gt_biomarkers: list[dict[str, str]]) -> list[BiomarkerCandidate]:
    """Convert GT biomarker dicts to mock BiomarkerCandidates for dry-run self-comparison."""
    return [
        BiomarkerCandidate(
            raw_name=bm.get("original_name", ""),
            raw_value=bm.get("original_value", ""),
            raw_unit=bm.get("original_unit", ""),
            raw_reference_range=bm.get("original_range", ""),
            collection_date=bm.get("collection_date", ""),
            lab_source=bm.get("lab_source", ""),
            llm_confidence=100.0,
            source_page=None,
            composite_confidence=100.0,
            band=Band.AUTO_ACCEPT,
        )
        for bm in gt_biomarkers
    ]
