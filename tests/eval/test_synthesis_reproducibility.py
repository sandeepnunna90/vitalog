"""AC4 — same seed produces byte-identical output."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.eval.synthesis.vendor_templates.hospital import generate_report as generate_hospital_report
from src.eval.synthesis.vendor_templates.quest import generate_report


def test_pdf_byte_identical_for_same_seed(tmp_path: Path) -> None:
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"
    dir_a.mkdir()
    dir_b.mkdir()

    pdf_a, _ = generate_report(42, dir_a)
    pdf_b, _ = generate_report(42, dir_b)

    assert pdf_a.read_bytes() == pdf_b.read_bytes()


def test_ground_truth_byte_identical_for_same_seed(tmp_path: Path) -> None:
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"
    dir_a.mkdir()
    dir_b.mkdir()

    _, gt_a = generate_report(42, dir_a)
    _, gt_b = generate_report(42, dir_b)

    assert gt_a.read_bytes() == gt_b.read_bytes()


def test_different_seeds_produce_different_pdfs(tmp_path: Path) -> None:
    pdf_a, _ = generate_report(1, tmp_path)
    pdf_b, _ = generate_report(2, tmp_path)

    assert pdf_a.read_bytes() != pdf_b.read_bytes()


def test_different_seeds_produce_different_ground_truth(tmp_path: Path) -> None:
    _, gt_a = generate_report(1, tmp_path)
    _, gt_b = generate_report(2, tmp_path)

    assert gt_a.read_bytes() != gt_b.read_bytes()


@pytest.mark.parametrize("seed", [42, 300])
def test_hospital_pdf_byte_identical_for_same_seed(tmp_path: Path, seed: int) -> None:
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"
    dir_a.mkdir()
    dir_b.mkdir()

    pdf_a, _ = generate_hospital_report(seed, dir_a)
    pdf_b, _ = generate_hospital_report(seed, dir_b)

    assert pdf_a.read_bytes() == pdf_b.read_bytes()


def test_hospital_different_seeds_produce_different_pdfs(tmp_path: Path) -> None:
    pdf_a, _ = generate_hospital_report(300, tmp_path)
    pdf_b, _ = generate_hospital_report(301, tmp_path)

    assert pdf_a.read_bytes() != pdf_b.read_bytes()
