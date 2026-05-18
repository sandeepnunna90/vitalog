"""Unit tests for src/eval/harness/reporter.py (file I/O paths)."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from src.eval.harness.aggregator import AggregateReport, DocResult, aggregate
from src.eval.harness.comparator import DocComparison
from src.eval.harness.reporter import append_history, write_report

# ── Fixtures ─────────────────────────────────────────────────────────────────


def _empty_comparison() -> DocComparison:
    return DocComparison(biomarker_matches=[], extra_extracted=0, band_distribution={})


def _make_report(run_id: str = "20260101T000000Z") -> AggregateReport:
    doc_results = [
        DocResult(
            filename="test.pdf",
            split="synthetic",
            vendor="quest",
            expected_classification="lab_report",
            actual_classification="lab_report",
            classification_correct=True,
            comparison=_empty_comparison(),
        )
    ]
    return aggregate(doc_results, run_id)


# ── write_report ─────────────────────────────────────────────────────────────


def test_write_report_creates_json(tmp_path: Path) -> None:
    report = _make_report()
    write_report(report, tmp_path / "run1")
    json_path = tmp_path / "run1" / "accuracy.json"
    assert json_path.exists()
    data = json.loads(json_path.read_text())
    assert data["run_id"] == report.run_id
    assert data["total_docs"] == 1


def test_write_report_creates_markdown(tmp_path: Path) -> None:
    report = _make_report()
    write_report(report, tmp_path / "run1")
    md_path = tmp_path / "run1" / "accuracy.md"
    assert md_path.exists()
    content = md_path.read_text()
    assert "# Accuracy Report" in content
    assert "## Overall" in content
    assert "## Split: synthetic" in content


def test_write_report_creates_output_dir(tmp_path: Path) -> None:
    report = _make_report()
    nested = tmp_path / "a" / "b" / "run1"
    write_report(report, nested)
    assert nested.is_dir()


# ── append_history ────────────────────────────────────────────────────────────


def test_append_history_creates_file_with_header(tmp_path: Path) -> None:
    report = _make_report("20260101T000000Z")
    append_history(report, tmp_path)
    history = tmp_path / "history.csv"
    assert history.exists()
    rows = list(csv.DictReader(history.open()))
    assert len(rows) == 1
    assert rows[0]["timestamp"] == "20260101T000000Z"


def test_append_history_appends_on_second_call(tmp_path: Path) -> None:
    append_history(_make_report("20260101T000000Z"), tmp_path)
    append_history(_make_report("20260102T000000Z"), tmp_path)
    rows = list(csv.DictReader((tmp_path / "history.csv").open()))
    assert len(rows) == 2
    assert rows[1]["timestamp"] == "20260102T000000Z"


def test_append_history_header_written_once(tmp_path: Path) -> None:
    append_history(_make_report("run1"), tmp_path)
    append_history(_make_report("run2"), tmp_path)
    lines = (tmp_path / "history.csv").read_text().splitlines()
    header_count = sum(1 for ln in lines if ln.startswith("timestamp"))
    assert header_count == 1


def test_append_history_overall_f1_zero_for_empty_doc(tmp_path: Path) -> None:
    report = _make_report()
    append_history(report, tmp_path)
    rows = list(csv.DictReader((tmp_path / "history.csv").open()))
    assert float(rows[0]["overall_f1"]) == 0.0


def test_append_history_prompt_versions_json_is_valid_json(tmp_path: Path) -> None:
    report = _make_report()
    append_history(report, tmp_path)
    rows = list(csv.DictReader((tmp_path / "history.csv").open()))
    versions = json.loads(rows[0]["prompt_versions_json"])
    assert isinstance(versions, dict)
