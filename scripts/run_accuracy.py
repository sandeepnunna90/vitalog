#!/usr/bin/env python3
"""Run extraction accuracy harness against the eval corpus.

Dry-run (no API calls — validates report shape and ~100% F1):
    python scripts/run_accuracy.py --corpus eval_corpus/ --dry-run

Live run (requires AWS + Anthropic credentials, ~$1-2 per full run):
    python scripts/run_accuracy.py --corpus eval_corpus/
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path


def _build_pipeline() -> object:
    """Instantiate full D1–D6 pipeline from environment credentials."""
    import os

    from src.gateway.gateway import Gateway
    from src.ingestion.classifier import DocumentClassifier
    from src.ingestion.structurer import Structurer
    from src.ingestion.textract_adapter import TextractAdapter
    from src.ingestion.textract_fallback import TextractFallbackAdapter
    from src.ingestion.upload_validator import UploadValidator

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    gateway = Gateway(api_key=api_key)

    class _NoopAuditRepo:
        def record(self, actor: str, event: str, details: object) -> None:
            pass

    from src.eval.harness.runner import Pipeline

    return Pipeline(
        validator=UploadValidator(),
        classifier=DocumentClassifier(gateway),
        textract=TextractAdapter(),
        fallback=TextractFallbackAdapter(gateway),
        structurer=Structurer(gateway, audit_repo=_NoopAuditRepo()),
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run extraction accuracy harness against the eval corpus."
    )
    parser.add_argument(
        "--corpus",
        type=Path,
        required=True,
        help="Path to the eval corpus root directory (contains manifest.json).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Skip the pipeline entirely: compare ground truth against itself "
            "to validate report shape (no API calls, ~100%% F1 expected)."
        ),
    )
    args = parser.parse_args()

    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir = args.corpus / "runs" / run_id

    from src.eval.harness.aggregator import aggregate
    from src.eval.harness.reporter import append_history, write_report
    from src.eval.harness.runner import HarnessRunner, Pipeline

    pipeline: Pipeline | None = None
    if not args.dry_run:
        pipeline = _build_pipeline()  # type: ignore[assignment]

    runner = HarnessRunner(args.corpus, dry_run=args.dry_run, pipeline=pipeline)

    mode = "DRY-RUN" if args.dry_run else "LIVE"
    print(f"[{mode}] Running harness against {args.corpus} ...")
    doc_results = runner.run_all()

    report = aggregate(doc_results, run_id)

    print(f"\nResults — {report.total_docs} documents")
    print(f"{'Field':<10} {'Precision':>10} {'Recall':>8} {'F1':>8}")
    print("-" * 40)
    for m in report.overall:
        print(f"{m.field:<10} {m.precision:>10.3f} {m.recall:>8.3f} {m.f1:>8.3f}")

    write_report(report, out_dir)
    append_history(report, args.corpus)

    print(f"\nReport written to: {out_dir}/accuracy.md")
    print(f"History appended: {args.corpus}/history.csv")


if __name__ == "__main__":
    main()
