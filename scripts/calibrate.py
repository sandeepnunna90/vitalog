#!/usr/bin/env python3
"""C5 confidence-band calibration script.

Dry-run (no API calls — validates calibration plumbing with GT self-comparison):
    python scripts/calibrate.py --dry-run

Live run (requires AWS + Anthropic credentials, ~$1-2):
    python scripts/calibrate.py

Both modes write eval_corpus/calibration_report.md and update
src/ingestion/structurer.py threshold constants if a qualifying pair is found.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from src._paths import PROJECT_ROOT


def _build_pipeline() -> object:
    import os
    from typing import cast

    from src.gateway.gateway import Gateway
    from src.ingestion.classifier import DocumentClassifier
    from src.ingestion.structurer import Structurer
    from src.ingestion.textract_adapter import TextractAdapter
    from src.ingestion.textract_fallback import TextractFallbackAdapter
    from src.ingestion.upload_validator import UploadValidator
    from src.persistence.audit_log_repository import AuditLogRepository

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    gateway = Gateway(api_key=api_key)

    class _NoopAuditRepo:
        def record(self, actor: str, event: str, details: object) -> None:
            pass

    audit_repo = cast(AuditLogRepository, _NoopAuditRepo())
    from src.eval.harness.runner import Pipeline

    return Pipeline(
        validator=UploadValidator(),
        classifier=DocumentClassifier(gateway),
        textract=TextractAdapter(audit_repo),
        fallback=TextractFallbackAdapter(gateway, audit_repo),
        structurer=Structurer(gateway, audit_repo=audit_repo),
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="C5 confidence-band calibration: sweep threshold grid, pick best pair."
    )
    parser.add_argument(
        "--corpus",
        type=Path,
        default=PROJECT_ROOT / "eval_corpus",
        help="Path to eval corpus root (default: eval_corpus/).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="GT self-comparison — no API calls, validates calibration plumbing.",
    )
    args = parser.parse_args()

    corpus_root: Path = args.corpus
    report_path = corpus_root / "calibration_report.md"
    structurer_path = PROJECT_ROOT / "src" / "ingestion" / "structurer.py"

    from src.eval.calibration.grid_search import (
        THRESHOLDS_AUTO_ACCEPT,
        THRESHOLDS_REJECT,
        pick_best,
        run_grid,
    )
    from src.eval.calibration.report_writer import write_constants, write_report
    from src.eval.harness.runner import HarnessRunner

    pipeline = None if args.dry_run else _build_pipeline()
    mode = "DRY-RUN" if args.dry_run else "LIVE"
    print(f"[{mode}] Running harness against {corpus_root} ...")

    runner = HarnessRunner(corpus_root, dry_run=args.dry_run, pipeline=pipeline)
    doc_results = runner.run_all()

    cells = run_grid(doc_results)
    best = pick_best(cells)

    print("\nGrid summary (aa_prec / aa_recall / review_prec):")
    cell_map = {(c.threshold_auto_accept, c.threshold_reject): c for c in cells}
    header = f"{'ta/tr':>8}" + "".join(f"  {tr:>5.0f}" for tr in THRESHOLDS_REJECT)
    print(header)
    for ta in THRESHOLDS_AUTO_ACCEPT:
        row = f"{ta:>8.0f}"
        for tr in THRESHOLDS_REJECT:
            c = cell_map[(ta, tr)]
            row += f"  {c.aa_precision:.2f}/{c.aa_recall:.2f}/{c.review_precision:.2f}"
        print(row)

    if args.dry_run:
        print("\n[DRY-RUN] Grid search complete — report and constants NOT updated.")
        print("Run without --dry-run to calibrate against the live pipeline.")
        return

    write_report(cells, best, report_path)
    print(f"\nReport written: {report_path}")

    if best:
        print(
            f"Chosen pair: THRESHOLD_AUTO_ACCEPT={best.threshold_auto_accept:.1f},"
            f" THRESHOLD_REJECT={best.threshold_reject:.1f}"
        )
        print(
            f"  aa_precision={best.aa_precision:.4f},"
            f" aa_recall={best.aa_recall:.4f},"
            f" review_precision={best.review_precision:.4f}"
        )
        write_constants(best.threshold_auto_accept, best.threshold_reject, structurer_path)
        print(f"Constants updated in {structurer_path}")
    else:
        print(
            "\n⚠  CALIBRATION FAILED — no grid cell met aa_recall >= 0.95 "
            "AND review_precision >= 0.80."
        )
        print("Falling back to initial constants (95.0, 70.0). See calibration_report.md.")


if __name__ == "__main__":
    main()
