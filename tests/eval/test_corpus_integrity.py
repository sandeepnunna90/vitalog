"""Corpus integrity tests — verifies every eval_corpus file matches manifest.json.

Fails loudly if any corpus file is modified without re-running build_manifest.py.
Skipped when manifest.json does not yet exist (corpus not yet assembled).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

CORPUS_ROOT = Path(__file__).parent.parent.parent / "eval_corpus"
MANIFEST_PATH = CORPUS_ROOT / "manifest.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def manifest() -> dict:
    if not MANIFEST_PATH.exists():
        pytest.skip("eval_corpus/manifest.json not found — run scripts/build_manifest.py first")
    return json.loads(MANIFEST_PATH.read_text())


def test_manifest_has_documents(manifest: dict) -> None:
    assert manifest["total_documents"] > 0, "Manifest lists no documents"
    assert len(manifest["documents"]) == manifest["total_documents"]


def test_all_splits_represented(manifest: dict) -> None:
    splits = {d["split"] for d in manifest["documents"]}
    # redacted_real may be absent until user provides PDFs
    assert "synthetic" in splits, "No synthetic docs in manifest"
    assert "adversarial" in splits, "No adversarial docs in manifest"


@pytest.mark.parametrize(
    "entry",
    pytest.lazy_fixture("manifest") if False else [],  # populated dynamically below
)
def test_file_hashes_match_manifest(entry: dict) -> None:
    pass  # replaced by the parametrized test below


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """Dynamically parametrize hash tests from manifest at collection time."""
    if metafunc.function.__name__ != "test_corpus_file_hash":
        return
    if not MANIFEST_PATH.exists():
        metafunc.parametrize("entry", [])
        return
    docs = json.loads(MANIFEST_PATH.read_text())["documents"]
    metafunc.parametrize("entry", docs, ids=[d["filename"] for d in docs])


def test_corpus_file_hash(entry: dict) -> None:
    split = entry["split"]
    filename = entry["filename"]
    pdf_path = CORPUS_ROOT / split / filename

    assert pdf_path.exists(), f"Corpus file missing: {split}/{filename}"
    actual = _sha256(pdf_path)
    assert actual == entry["pdf_sha256"], (
        f"{filename}: hash mismatch — file was modified after manifest was built. "
        "Re-run scripts/build_manifest.py if the change was intentional."
    )

    if "ground_truth_sha256" in entry:
        gt_path = pdf_path.with_suffix("").with_suffix(".ground_truth.json")
        assert gt_path.exists(), f"Ground truth missing: {gt_path.name}"
        gt_actual = _sha256(gt_path)
        assert gt_actual == entry["ground_truth_sha256"], (
            f"{gt_path.name}: hash mismatch — re-run scripts/build_manifest.py."
        )
