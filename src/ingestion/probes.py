"""Pre-LLM probes: text-extractability for PDFs, resolution check for images.

probe_pdf  — imported by D2 (classifier) as well as D1 (validator)
probe_image — D1 only

Both fitz and PIL imports are deferred inside the functions so that importing
this module never fails in environments where those packages are absent.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_MIN_RESOLUTION = 600  # pixels; both width and height must meet this threshold


def probe_pdf(file_bytes: bytes) -> bool:
    """Return True if PyMuPDF finds any extractable text on any page.

    Returns False for scanned/image-only PDFs — the caller should plan for
    vision-LLM fallback (D5).
    """
    import fitz  # pymupdf

    doc = fitz.open(stream=file_bytes, filetype="pdf")
    try:
        for page in doc:
            if page.get_text().strip():
                return True
        return False
    finally:
        doc.close()


def probe_image(file_bytes: bytes, mime: str) -> str | None:
    """Return a warning string if the image is below 600×600, else None.

    Raises:
        ImportError: for HEIC files when pillow-heif is not installed.
            The caller (upload_validator) converts this to UnsupportedFormatError.
    """
    import io

    if mime == "image/heic":
        import pillow_heif

        pillow_heif.register_heif_opener()

    from PIL import Image

    img = Image.open(io.BytesIO(file_bytes))
    width, height = img.size
    if width < _MIN_RESOLUTION or height < _MIN_RESOLUTION:
        warning = (
            f"Image resolution {width}×{height} is below the recommended "
            f"{_MIN_RESOLUTION}×{_MIN_RESOLUTION}. OCR quality may be poor."
        )
        logger.warning("LowResolutionWarning: %s", warning)
        return warning
    return None
