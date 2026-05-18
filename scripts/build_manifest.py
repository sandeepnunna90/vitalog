#!/usr/bin/env python3
"""Build eval_corpus/manifest.json by hashing every file in the corpus splits.

Run after assembling all three corpus splits:
    python scripts/build_manifest.py

Re-run whenever the corpus changes. The integrity test (tests/eval/test_corpus_integrity.py)
will fail if any corpus file's hash diverges from the manifest.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

CORPUS_ROOT = Path("eval_corpus")
SPLITS = ("synthetic", "redacted_real", "adversarial")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _vendor_from_path(pdf_path: Path) -> str:
    """Infer vendor tag from filename or parent directory name."""
    name = pdf_path.stem.lower()
    if "quest" in name or "synthetic" in name:
        return "quest"
    if "labcorp" in name:
        return "labcorp"
    if "hospital" in name or "memorial" in name:
        return "hospital"
    # Adversarial docs — tag by adversarial type
    if "photo" in name:
        return "quest-image"
    if "multipage" in name:
        return "quest-multipage"
    if "mmol" in name:
        return "quest-mmol"
    return "unknown"


def _expected_classification(split: str, pdf_path: Path) -> str:
    if split == "adversarial" and "multipage" in pdf_path.stem:
        return "lab_report"  # leading page is lab_report
    return "lab_report"  # all corpus docs are lab reports


def build_manifest() -> dict:
    documents = []
    for split in SPLITS:
        split_dir = CORPUS_ROOT / split
        if not split_dir.exists():
            continue
        for pdf_path in sorted(split_dir.glob("*.pdf")):
            gt_path = pdf_path.with_suffix("").with_suffix(".ground_truth.json")
            entry: dict = {
                "split": split,
                "vendor": _vendor_from_path(pdf_path),
                "filename": pdf_path.name,
                "expected_classification": _expected_classification(split, pdf_path),
                "pdf_sha256": _sha256(pdf_path),
            }
            if gt_path.exists():
                entry["ground_truth_sha256"] = _sha256(gt_path)
            documents.append(entry)

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "total_documents": len(documents),
        "documents": documents,
    }


def main() -> None:
    manifest = build_manifest()
    out_path = CORPUS_ROOT / "manifest.json"
    out_path.write_text(json.dumps(manifest, indent=2))
    print(f"Manifest written: {out_path}  ({manifest['total_documents']} documents)")


if __name__ == "__main__":
    main()
