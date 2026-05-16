"""Shared binary fixtures for the ingestion test suite.

All fixtures generate bytes programmatically — no binary assets committed to the repo.
Uses reportlab (already in deps) for PDFs and Pillow for images.
"""

from __future__ import annotations

import io

import pytest
from PIL import Image  # type: ignore[import-untyped]  # noqa: E402

# ── PDF fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture()
def text_pdf_bytes() -> bytes:
    """A minimal valid PDF with real extractable text."""
    from reportlab.pdfgen import canvas  # type: ignore[import-untyped]

    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(100, 750, "HbA1c: 6.8%  LDL: 110 mg/dL  Glucose: 94 mg/dL")
    c.save()
    return buf.getvalue()


@pytest.fixture()
def image_pdf_bytes() -> bytes:
    """A PDF built from an embedded PNG — PyMuPDF finds zero extractable text."""
    from reportlab.lib.units import inch  # type: ignore[import-untyped]
    from reportlab.lib.utils import ImageReader  # type: ignore[import-untyped]
    from reportlab.pdfgen import canvas  # type: ignore[import-untyped]

    img_buf = io.BytesIO()
    Image.new("RGB", (200, 200), color=(180, 180, 180)).save(img_buf, format="PNG")
    img_buf.seek(0)

    pdf_buf = io.BytesIO()
    c = canvas.Canvas(pdf_buf)
    c.drawImage(ImageReader(img_buf), 0, 0, width=2 * inch, height=2 * inch)
    c.save()
    return pdf_buf.getvalue()


# ── Image fixtures ────────────────────────────────────────────────────────────


@pytest.fixture()
def high_res_jpeg_bytes() -> bytes:
    """A valid JPEG at 800×800 (above the 600×600 warning threshold)."""
    buf = io.BytesIO()
    Image.new("RGB", (800, 800), color=(100, 150, 200)).save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture()
def low_res_jpeg_bytes() -> bytes:
    """A valid JPEG at 400×400 (below threshold — triggers LowResolutionWarning)."""
    buf = io.BytesIO()
    Image.new("RGB", (400, 400), color=(255, 100, 100)).save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture()
def high_res_png_bytes() -> bytes:
    """A valid PNG at 1000×1000."""
    buf = io.BytesIO()
    Image.new("RGB", (1000, 1000), color=(50, 200, 50)).save(buf, format="PNG")
    return buf.getvalue()


# ── Bad-file fixtures ─────────────────────────────────────────────────────────


@pytest.fixture()
def corrupt_pdf_bytes() -> bytes:
    """Bytes starting with %PDF- header but otherwise garbage (not parseable)."""
    return b"%PDF-1.4 this is not a valid pdf\n" + b"\x00" * 64


@pytest.fixture()
def corrupt_image_bytes() -> bytes:
    """JPEG magic bytes followed by corrupt body (Pillow cannot decode)."""
    return b"\xff\xd8\xff\xe0" + b"\x00" * 32


@pytest.fixture()
def empty_bytes() -> bytes:
    return b""


@pytest.fixture()
def docx_bytes() -> bytes:
    """Minimal DOCX-like bytes (PK ZIP magic) — unsupported format."""
    return b"PK\x03\x04" + b"\x00" * 30


@pytest.fixture()
def oversized_pdf_bytes(text_pdf_bytes: bytes) -> bytes:
    """A valid PDF padded to just over 20 MB."""
    return text_pdf_bytes + b"\x00" * (20 * 1024 * 1024 + 1)
