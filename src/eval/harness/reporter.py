"""Emit accuracy.json, accuracy.md, and append to history.csv."""

from __future__ import annotations

import csv
import json
import subprocess
from dataclasses import asdict
from pathlib import Path

from src.eval.harness.aggregator import AggregateReport, FieldMetrics


def write_report(report: AggregateReport, out_dir: Path) -> None:
    """Write accuracy.json and accuracy.md to out_dir (created if absent)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_json(report, out_dir / "accuracy.json")
    _write_markdown(report, out_dir / "accuracy.md")


def append_history(report: AggregateReport, corpus_root: Path) -> None:
    """Append one row to eval_corpus/history.csv (created with header on first call).

    The first row in the committed history.csv is a dry-run seed (git_sha from C2)
    written during C3 harness validation — not a live pipeline run.
    """
    history_path = corpus_root / "history.csv"
    field_names = [
        "timestamp",
        "git_sha",
        "prompt_versions_json",
        "name_f1",
        "value_f1",
        "unit_f1",
        "range_f1",
        "date_f1",
        "overall_f1",
    ]

    overall_by_field = {m.field: m.f1 for m in report.overall}
    field_f1s = [overall_by_field.get(f, 0.0) for f in ("name", "value", "unit", "range", "date")]
    overall_f1 = sum(field_f1s) / len(field_f1s) if field_f1s else 0.0

    row = {
        "timestamp": report.run_id,
        "git_sha": _git_sha(),
        "prompt_versions_json": json.dumps(_prompt_versions(corpus_root.parent)),
        "name_f1": round(overall_by_field.get("name", 0.0), 4),
        "value_f1": round(overall_by_field.get("value", 0.0), 4),
        "unit_f1": round(overall_by_field.get("unit", 0.0), 4),
        "range_f1": round(overall_by_field.get("range", 0.0), 4),
        "date_f1": round(overall_by_field.get("date", 0.0), 4),
        "overall_f1": round(overall_f1, 4),
    }

    write_header = not history_path.exists()
    with history_path.open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=field_names)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


# ── Private helpers ───────────────────────────────────────────────────────────


def _write_json(report: AggregateReport, path: Path) -> None:
    def _serialise(obj: object) -> object:
        if hasattr(obj, "__dataclass_fields__"):
            return asdict(obj)  # type: ignore[call-overload]
        raise TypeError(f"Not serialisable: {type(obj)}")

    path.write_text(json.dumps(asdict(report), indent=2, default=_serialise))


def _write_markdown(report: AggregateReport, path: Path) -> None:
    lines: list[str] = [
        f"# Accuracy Report — {report.run_id}",
        "",
        f"**Total documents:** {report.total_docs}",
        "",
        "## Overall (all splits)",
        "",
        _metrics_table(report.overall),
        "",
    ]

    for split, metrics in sorted(report.by_split.items()):
        doc_count = sum(1 for r in report.doc_results if r.split == split)
        lines += [
            f"## Split: {split}  ({doc_count} docs)",
            "",
            _metrics_table(metrics),
            "",
        ]

    if report.by_band:
        lines += ["## By confidence band (matched pairs only)", ""]
        for band, metrics in sorted(report.by_band.items()):
            lines += [
                f"### Band: {band}",
                "",
                _metrics_table(metrics),
                "",
            ]

    lines += ["## Per-document results", ""]
    lines.append("| File | Split | Expected | Actual | Correct |")
    lines.append("|---|---|---|---|---|")
    for r in report.doc_results:
        tick = "✓" if r.classification_correct else "✗"
        lines.append(
            f"| {r.filename} | {r.split} | {r.expected_classification}"
            f" | {r.actual_classification} | {tick} |"
        )

    path.write_text("\n".join(lines) + "\n")


def _metrics_table(metrics: list[FieldMetrics]) -> str:
    header = "| Field | TP | FP | FN | Precision | Recall | F1 |"
    sep = "|---|---|---|---|---|---|---|"
    rows = [
        f"| {m.field} | {m.tp} | {m.fp} | {m.fn}"
        f" | {m.precision:.3f} | {m.recall:.3f} | {m.f1:.3f} |"
        for m in metrics
    ]
    return "\n".join([header, sep] + rows)


def _git_sha() -> str:
    try:
        return (
            subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL)
            .decode()
            .strip()
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def _prompt_versions(project_root: Path) -> dict[str, str]:
    """Walk prompts/ directory and collect {concern: version} from filenames like v1.md."""
    prompts_dir = project_root / "prompts"
    versions: dict[str, str] = {}
    if not prompts_dir.exists():
        return versions
    for md_file in sorted(prompts_dir.rglob("*.md")):
        parts = md_file.relative_to(prompts_dir).parts
        if len(parts) == 2:  # prompts/<concern>/v1.md
            concern = parts[0]
            version = md_file.stem  # "v1"
            versions[concern] = version
    return versions
