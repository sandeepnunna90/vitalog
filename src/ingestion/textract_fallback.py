"""Vision-LLM fallback for low-confidence Textract output (ADR-02, D5).

TextractFallbackAdapter.extract() checks whether the primary Textract result's
minimum field confidence falls below THRESHOLD_FALLBACK. If so, it sends the
original document image to Claude with vision via Gateway.call() and normalizes
the LLM output into the same TextractResult shape, so downstream code (D6) sees
a uniform interface regardless of which path ran.
"""

from __future__ import annotations

import base64
import time
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.ingestion.textract_schemas import Block, KVPair, Table, TableCell, TextractResult
from src.ingestion.upload_validator import ValidatedUpload

# Calibrated against the eval set in C5. Matches the auto-accept band lower bound
# (architecture §5.1): if any field is below this, we can't auto-accept, so the
# vision fallback runs to try for a higher-quality extraction.
THRESHOLD_FALLBACK: float = 95.0

# Anthropic-supported image media types (vision API constraint).
_SUPPORTED_MEDIA_TYPES: frozenset[str] = frozenset(
    {"image/jpeg", "image/png", "image/gif", "image/webp"}
)


# ── Fallback output schema (Gateway tool-use) ─────────────────────────────────


class FallbackKVPair(BaseModel):
    model_config = ConfigDict(strict=True)

    key: str
    value: str
    confidence: float = Field(ge=0.0, le=100.0)  # LLM self-reported 0–100 scale


class FallbackRow(BaseModel):
    model_config = ConfigDict(strict=True)

    cells: list[str]


class FallbackTable(BaseModel):
    model_config = ConfigDict(strict=True)

    rows: list[FallbackRow]
    confidence: float = Field(ge=0.0, le=100.0)  # LLM self-reported 0–100 scale


class FallbackExtractionResult(BaseModel):
    """Schema returned by the vision-LLM extraction prompt.

    Converted to TextractResult by _to_textract_result() so D6 sees a uniform
    interface regardless of which OCR path produced the data.
    """

    model_config = ConfigDict(strict=True)

    text_lines: list[str]  # Verbatim text lines extracted from the document
    kv_pairs: list[FallbackKVPair]
    tables: list[FallbackTable]
    overall_confidence: float = Field(ge=0.0, le=100.0)  # 0–100 LLM self-reported
    extraction_notes: str  # Quality issues or unreadable regions; empty string if none


# ── Adapter ───────────────────────────────────────────────────────────────────


class TextractFallbackAdapter:
    """Conditionally replaces a low-confidence TextractResult with a vision-LLM extraction."""

    def __init__(
        self,
        gateway: Any,  # Gateway — imported lazily to avoid circular deps in tests
        audit_repo: Any,  # AuditLogRepository
    ) -> None:
        self._gateway = gateway
        self._audit = audit_repo

    def extract(
        self,
        upload: ValidatedUpload,
        document_id: uuid.UUID,
        textract_result: TextractResult,
    ) -> TextractResult:
        """Return textract_result unchanged if min_confidence >= THRESHOLD_FALLBACK.

        Otherwise, invoke the vision-LLM via Gateway and return the result
        normalized to TextractResult (same shape as the primary path).
        """
        min_conf = _compute_min_confidence(textract_result)

        if min_conf >= THRESHOLD_FALLBACK:
            self._audit.record(
                "system",
                "vision_fallback_skipped",
                {
                    "document_id": str(document_id),
                    "min_confidence": min_conf,
                    "threshold": THRESHOLD_FALLBACK,
                },
            )
            return textract_result

        start = time.monotonic()
        image_content = self._build_image_content(upload)
        fallback: FallbackExtractionResult = self._gateway.call(
            prompt_id="extraction",
            version="v1",
            inputs={},
            output_schema=FallbackExtractionResult,
            image_content=image_content,
        )
        latency_ms = int((time.monotonic() - start) * 1000)

        self._audit.record(
            "system",
            "vision_fallback_invoked",
            {
                "document_id": str(document_id),
                "min_confidence_textract": min_conf,
                "threshold": THRESHOLD_FALLBACK,
                "fallback_overall_confidence": fallback.overall_confidence,
                "latency_ms": latency_ms,
            },
        )
        return _to_textract_result(fallback)

    def _build_image_content(self, upload: ValidatedUpload) -> list[dict[str, Any]]:
        """Build the image content block for Gateway.call(image_content=...)."""
        if upload.mime not in _SUPPORTED_MEDIA_TYPES:
            # PDF and HEIC are not accepted by the Anthropic vision API directly.
            # PyMuPDF can open both formats, so render page 1 to PNG in all cases.
            img_bytes, media_type = _pdf_to_png(upload.file_bytes)
        else:
            img_bytes = upload.file_bytes
            media_type = upload.mime

        encoded = base64.standard_b64encode(img_bytes).decode("ascii")
        return [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": encoded,
                },
            }
        ]


# ── Module-level helpers ──────────────────────────────────────────────────────


def _compute_min_confidence(result: TextractResult) -> float:
    """Return the minimum confidence across all fields in the TextractResult.

    Empty result returns 0.0, which guarantees the fallback triggers — a
    document that produced nothing from Textract should always be re-attempted
    with vision. Mirrors _compute_textract_floor in structurer.py; kept
    separate to avoid cross-module coupling between two independent adapters.
    """
    all_confs: list[float] = (
        [b.confidence for b in result.blocks]
        + [c.confidence for t in result.tables for row in t.rows for c in row]
        + [kv.key_confidence for kv in result.kv_pairs]
        + [kv.value_confidence for kv in result.kv_pairs]
    )
    return min(all_confs, default=0.0)


def _pdf_to_png(pdf_bytes: bytes) -> tuple[bytes, str]:
    """Render page 1 of a document to PNG at 2× zoom for Anthropic vision.

    Accepts any format PyMuPDF can open (PDF, HEIC, etc.).
    """
    import fitz  # PyMuPDF — deferred import to match project conventions

    with fitz.open(stream=pdf_bytes) as doc:
        page = doc[0]
        mat = fitz.Matrix(2, 2)  # 2× zoom ≈ 144 dpi; sufficient for lab report text
        pix = page.get_pixmap(matrix=mat)
        return pix.tobytes("png"), "image/png"


def _to_textract_result(fallback: FallbackExtractionResult) -> TextractResult:
    """Normalize FallbackExtractionResult into a TextractResult.

    Bounding boxes are None throughout — the vision LLM does not return spatial
    coordinates. page_count is always 1 (we send one image per call).
    """
    blocks = [
        Block(
            block_id=uuid.uuid4().hex,
            text=line,
            confidence=fallback.overall_confidence,
            bbox=None,
        )
        for line in fallback.text_lines
        if line.strip()
    ]

    kv_pairs = [
        KVPair(
            key=pair.key,
            value=pair.value,
            key_confidence=pair.confidence,
            value_confidence=pair.confidence,
            bbox=None,
        )
        for pair in fallback.kv_pairs
    ]

    tables = [
        Table(
            table_id=uuid.uuid4().hex,
            rows=[
                [
                    TableCell(
                        row_index=r_idx + 1,  # 1-based to match Textract convention
                        col_index=c_idx + 1,
                        text=cell,
                        confidence=tbl.confidence,
                        bbox=None,
                    )
                    for c_idx, cell in enumerate(row.cells)
                ]
                for r_idx, row in enumerate(tbl.rows)
            ],
            confidence=tbl.confidence,
        )
        for tbl in fallback.tables
    ]

    return TextractResult(
        blocks=blocks,
        tables=tables,
        kv_pairs=kv_pairs,
        page_count=1,
    )
