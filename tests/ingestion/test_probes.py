"""Unit tests for probe_pdf() and probe_image() — AC4 and AC5."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from src.ingestion.probes import probe_image, probe_pdf

# ── probe_pdf ─────────────────────────────────────────────────────────────────


def test_probe_pdf_text_extractable(text_pdf_bytes: bytes) -> None:
    """Text-bearing PDF → True."""
    assert probe_pdf(text_pdf_bytes) is True


def test_probe_pdf_image_only(image_pdf_bytes: bytes) -> None:
    """Image-only PDF → False (no extractable text)."""
    assert probe_pdf(image_pdf_bytes) is False


def test_probe_pdf_corrupt_raises(corrupt_pdf_bytes: bytes) -> None:
    """Corrupt bytes → fitz raises an exception."""
    with pytest.raises(Exception):  # noqa: B017
        probe_pdf(corrupt_pdf_bytes)


# ── probe_image ───────────────────────────────────────────────────────────────


def test_probe_image_high_res_no_warning(high_res_jpeg_bytes: bytes) -> None:
    """800×800 JPEG → no warning."""
    assert probe_image(high_res_jpeg_bytes, "image/jpeg") is None


def test_probe_image_low_res_returns_warning(low_res_jpeg_bytes: bytes) -> None:
    """400×400 JPEG → warning string mentioning the actual dimensions."""
    warning = probe_image(low_res_jpeg_bytes, "image/jpeg")
    assert warning is not None
    assert "400" in warning
    assert "600" in warning


def test_probe_image_exactly_600_no_warning() -> None:
    """600×600 exactly is not below threshold — no warning."""
    buf = io.BytesIO()
    Image.new("RGB", (600, 600)).save(buf, format="JPEG")
    assert probe_image(buf.getvalue(), "image/jpeg") is None


def test_probe_image_png_high_res(high_res_png_bytes: bytes) -> None:
    """1000×1000 PNG → no warning."""
    assert probe_image(high_res_png_bytes, "image/png") is None


def test_probe_image_width_too_small() -> None:
    """Width < 600 (height adequate) → warning."""
    buf = io.BytesIO()
    Image.new("RGB", (400, 800)).save(buf, format="JPEG")
    assert probe_image(buf.getvalue(), "image/jpeg") is not None


def test_probe_image_height_too_small() -> None:
    """Height < 600 (width adequate) → warning."""
    buf = io.BytesIO()
    Image.new("RGB", (800, 400)).save(buf, format="JPEG")
    assert probe_image(buf.getvalue(), "image/jpeg") is not None
