"""Unit tests for TextractFallbackAdapter (D5).

Gateway and AuditLogRepository are mocked — no real LLM calls or Supabase writes.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest

from src.ingestion.textract_fallback import (
    THRESHOLD_FALLBACK,
    FallbackExtractionResult,
    FallbackKVPair,
    FallbackRow,
    FallbackTable,
    TextractFallbackAdapter,
    _compute_min_confidence,
    _to_textract_result,
)

_PYMUPDF_PATH = "src.ingestion.textract_fallback._extract_with_pymupdf"
from src.ingestion.textract_schemas import Block, KVPair, Table, TableCell, TextractResult
from src.ingestion.upload_validator import ValidatedUpload

# ── Constants ─────────────────────────────────────────────────────────────────

_DOC_ID = uuid.UUID("00000000-0000-0000-0000-000000000005")
_PDF_BYTES = b"%PDF-1.4 fake pdf"
_JPEG_BYTES = b"\xff\xd8\xff fake jpeg"


# ── Helpers ───────────────────────────────────────────────────────────────────


def _empty_pymupdf() -> TextractResult:
    return TextractResult(blocks=[], tables=[], kv_pairs=[], page_count=0)


def _make_upload(mime: str = "application/pdf", file_bytes: bytes = _PDF_BYTES) -> ValidatedUpload:
    return ValidatedUpload(
        file_bytes=file_bytes,
        mime=mime,
        size_bytes=len(file_bytes),
        is_text_extractable=True,
        resolution_warning=None,
    )


def _make_adapter() -> tuple[TextractFallbackAdapter, MagicMock, MagicMock]:
    gateway = MagicMock()
    audit = MagicMock()
    adapter = TextractFallbackAdapter(gateway=gateway, audit_repo=audit)
    return adapter, gateway, audit


def _textract_result_with_confidence(conf: float) -> TextractResult:
    return TextractResult(
        blocks=[
            Block(block_id="b1", text="Glucose 98", confidence=conf, bbox=None),
        ],
        tables=[],
        kv_pairs=[],
        page_count=1,
    )


def _make_fallback_result(
    confidence: float = 80.0,
    text_lines: list[str] | None = None,
    kv_pairs: list[FallbackKVPair] | None = None,
    tables: list[FallbackTable] | None = None,
) -> FallbackExtractionResult:
    return FallbackExtractionResult(
        text_lines=text_lines or ["Glucose 98 mg/dL"],
        kv_pairs=kv_pairs or [FallbackKVPair(key="Glucose", value="98 mg/dL", confidence=75.0)],
        tables=tables or [],
        overall_confidence=confidence,
        extraction_notes="",
    )


# ── Tests: threshold decision ─────────────────────────────────────────────────


def test_high_confidence_skips_gateway() -> None:
    """min_confidence >= THRESHOLD_FALLBACK → no Gateway call, original result returned."""
    adapter, gateway, audit = _make_adapter()
    original = _textract_result_with_confidence(THRESHOLD_FALLBACK)

    result = adapter.extract(_make_upload(), _DOC_ID, original)

    gateway.call.assert_not_called()
    assert result is original


def test_high_confidence_writes_skipped_audit() -> None:
    adapter, _, audit = _make_adapter()
    original = _textract_result_with_confidence(THRESHOLD_FALLBACK)

    adapter.extract(_make_upload(), _DOC_ID, original)

    audit.record.assert_called_once()
    call_args = audit.record.call_args
    assert call_args[0][1] == "vision_fallback_skipped"
    assert call_args[0][2]["document_id"] == str(_DOC_ID)
    assert call_args[0][2]["min_confidence"] == THRESHOLD_FALLBACK


def test_low_confidence_invokes_gateway() -> None:
    """min_confidence < THRESHOLD_FALLBACK and PyMuPDF empty → Gateway.call() is invoked."""
    adapter, gateway, _ = _make_adapter()
    gateway.call.return_value = _make_fallback_result()
    low_conf_result = _textract_result_with_confidence(THRESHOLD_FALLBACK - 1.0)

    with patch(_PYMUPDF_PATH, return_value=_empty_pymupdf()):
        with patch.object(adapter, "_build_image_content", return_value=[{"type": "image"}]):
            adapter.extract(_make_upload(), _DOC_ID, low_conf_result)

    gateway.call.assert_called_once()
    call_kwargs = gateway.call.call_args[1]
    assert call_kwargs["prompt_id"] == "extraction"
    assert call_kwargs["version"] == "v1"
    assert call_kwargs["output_schema"] is FallbackExtractionResult


def test_low_confidence_writes_invoked_audit() -> None:
    adapter, gateway, audit = _make_adapter()
    gateway.call.return_value = _make_fallback_result(confidence=82.0)
    low_conf_result = _textract_result_with_confidence(70.0)

    with patch(_PYMUPDF_PATH, return_value=_empty_pymupdf()):
        with patch.object(adapter, "_build_image_content", return_value=[]):
            adapter.extract(_make_upload(), _DOC_ID, low_conf_result)

    audit.record.assert_called_once()
    last_call = audit.record.call_args
    assert last_call[0][1] == "vision_fallback_invoked"
    payload = last_call[0][2]
    assert payload["document_id"] == str(_DOC_ID)
    assert payload["min_confidence_textract"] == 70.0
    assert payload["fallback_overall_confidence"] == 82.0
    assert "latency_ms" in payload


def test_empty_textract_result_triggers_fallback() -> None:
    """Empty TextractResult → min_confidence=0.0 → fallback always runs."""
    adapter, gateway, _ = _make_adapter()
    gateway.call.return_value = _make_fallback_result()
    empty = TextractResult(blocks=[], tables=[], kv_pairs=[], page_count=0)

    with patch(_PYMUPDF_PATH, return_value=_empty_pymupdf()):
        with patch.object(adapter, "_build_image_content", return_value=[]):
            adapter.extract(_make_upload(), _DOC_ID, empty)

    gateway.call.assert_called_once()


def test_pymupdf_success_skips_vision_llm() -> None:
    """PyMuPDF extracts enough text → vision LLM not called."""
    adapter, gateway, audit = _make_adapter()
    low_conf = _textract_result_with_confidence(50.0)
    rich_result = TextractResult(
        blocks=[Block(block_id="b1", text="A" * 100, confidence=95.0, bbox=None)],
        tables=[],
        kv_pairs=[],
        page_count=2,
    )

    with patch(_PYMUPDF_PATH, return_value=rich_result):
        result = adapter.extract(_make_upload(), _DOC_ID, low_conf)

    gateway.call.assert_not_called()
    assert result is rich_result
    audit.record.assert_called_once()
    assert audit.record.call_args[0][1] == "pymupdf_fallback_invoked"


def test_threshold_boundary_exactly_95_no_fallback() -> None:
    """Exactly THRESHOLD_FALLBACK (95.0) → no fallback (condition is >=, not >)."""
    adapter, gateway, _ = _make_adapter()
    result = _textract_result_with_confidence(95.0)

    adapter.extract(_make_upload(), _DOC_ID, result)

    gateway.call.assert_not_called()


# ── Tests: result conversion ──────────────────────────────────────────────────


def test_fallback_result_converts_to_textract_result() -> None:
    """_to_textract_result() produces a TextractResult with correct structure."""
    fallback = FallbackExtractionResult(
        text_lines=["Line 1", "Line 2"],
        kv_pairs=[FallbackKVPair(key="HbA1c", value="6.1%", confidence=78.0)],
        tables=[
            FallbackTable(
                rows=[FallbackRow(cells=["Test", "Value", "Range"])],
                confidence=72.0,
            )
        ],
        overall_confidence=80.0,
        extraction_notes="slight blur in upper right corner",
    )

    result = _to_textract_result(fallback)

    assert isinstance(result, TextractResult)
    assert len(result.blocks) == 2
    assert result.blocks[0].text == "Line 1"
    assert result.blocks[0].confidence == 80.0
    assert result.blocks[0].bbox is None

    assert len(result.kv_pairs) == 1
    assert result.kv_pairs[0].key == "HbA1c"
    assert result.kv_pairs[0].key_confidence == 78.0
    assert result.kv_pairs[0].value_confidence == 78.0
    assert result.kv_pairs[0].bbox is None

    assert len(result.tables) == 1
    assert len(result.tables[0].rows) == 1
    assert result.tables[0].rows[0][0].text == "Test"
    assert result.tables[0].rows[0][0].row_index == 1
    assert result.tables[0].rows[0][0].col_index == 1
    assert result.tables[0].rows[0][0].confidence == 72.0
    assert result.tables[0].confidence == 72.0

    assert result.page_count == 1


def test_empty_fallback_result_gives_empty_textract_result() -> None:
    fallback = FallbackExtractionResult(
        text_lines=[],
        kv_pairs=[],
        tables=[],
        overall_confidence=0.0,
        extraction_notes="completely unreadable",
    )
    result = _to_textract_result(fallback)
    assert result.blocks == []
    assert result.kv_pairs == []
    assert result.tables == []
    assert result.page_count == 1


def test_whitespace_only_text_lines_excluded_from_blocks() -> None:
    """Blank or whitespace-only lines are stripped — they produce no Block."""
    fallback = FallbackExtractionResult(
        text_lines=["", "   ", "Real text"],
        kv_pairs=[],
        tables=[],
        overall_confidence=85.0,
        extraction_notes="",
    )
    result = _to_textract_result(fallback)
    assert len(result.blocks) == 1
    assert result.blocks[0].text == "Real text"


# ── Tests: image content building ────────────────────────────────────────────


def test_jpeg_upload_builds_jpeg_image_content() -> None:
    adapter, gateway, _ = _make_adapter()
    gateway.call.return_value = _make_fallback_result()
    upload = _make_upload(mime="image/jpeg", file_bytes=_JPEG_BYTES)
    low_conf = _textract_result_with_confidence(50.0)

    def capture(**kwargs: object) -> FallbackExtractionResult:
        capture.image_content = kwargs.get("image_content")  # type: ignore[attr-defined]
        return _make_fallback_result()

    gateway.call.side_effect = capture

    with patch(_PYMUPDF_PATH, return_value=_empty_pymupdf()):
        adapter.extract(upload, _DOC_ID, low_conf)

    content = capture.image_content  # type: ignore[attr-defined]
    assert content is not None
    assert len(content) == 1
    assert content[0]["type"] == "image"
    assert content[0]["source"]["type"] == "base64"
    assert content[0]["source"]["media_type"] == "image/jpeg"


def test_pdf_upload_builds_png_image_content() -> None:
    """PDF upload → rendered to PNG via PyMuPDF."""
    adapter, gateway, _ = _make_adapter()
    gateway.call.return_value = _make_fallback_result()
    upload = _make_upload(mime="application/pdf")
    low_conf = _textract_result_with_confidence(50.0)

    fake_png = b"\x89PNG fake"

    def capture(**kwargs: object) -> FallbackExtractionResult:
        capture.image_content = kwargs.get("image_content")  # type: ignore[attr-defined]
        return _make_fallback_result()

    gateway.call.side_effect = capture

    with patch(_PYMUPDF_PATH, return_value=_empty_pymupdf()):
        with patch("src.ingestion.textract_fallback._pdf_to_png", return_value=(fake_png, "image/png")):
            adapter.extract(upload, _DOC_ID, low_conf)

    content = capture.image_content  # type: ignore[attr-defined]
    assert content[0]["source"]["media_type"] == "image/png"


def test_heic_upload_builds_png_image_content() -> None:
    """HEIC upload → rendered to PNG via PyMuPDF (not sent as raw HEIC bytes)."""
    adapter, gateway, _ = _make_adapter()
    upload = _make_upload(mime="image/heic", file_bytes=b"fake heic bytes")
    low_conf = _textract_result_with_confidence(50.0)

    fake_png = b"\x89PNG fake"

    def capture(**kwargs: object) -> FallbackExtractionResult:
        capture.image_content = kwargs.get("image_content")  # type: ignore[attr-defined]
        return _make_fallback_result()

    gateway.call.side_effect = capture

    with patch(_PYMUPDF_PATH, return_value=_empty_pymupdf()):
        with patch("src.ingestion.textract_fallback._pdf_to_png", return_value=(fake_png, "image/png")):
            adapter.extract(upload, _DOC_ID, low_conf)

    content = capture.image_content  # type: ignore[attr-defined]
    assert content[0]["source"]["media_type"] == "image/png"


# ── Tests: _compute_min_confidence ────────────────────────────────────────────


def test_compute_min_confidence_uses_all_signal_types() -> None:
    """min across blocks + table cells + kv key + kv value confidences."""
    result = TextractResult(
        blocks=[Block(block_id="b1", text="x", confidence=99.0, bbox=None)],
        tables=[
            Table(
                table_id="t1",
                rows=[[TableCell(row_index=1, col_index=1, text="y", confidence=88.0, bbox=None)]],
                confidence=95.0,
            )
        ],
        kv_pairs=[
            KVPair(key="K", value="V", key_confidence=77.0, value_confidence=55.0, bbox=None)
        ],
        page_count=1,
    )
    assert _compute_min_confidence(result) == 55.0


def test_compute_min_confidence_empty_returns_zero() -> None:
    empty = TextractResult(blocks=[], tables=[], kv_pairs=[], page_count=0)
    assert _compute_min_confidence(empty) == 0.0


# ── Tests: error propagation ───────────────────────────────────────────────────


def test_gateway_error_propagates() -> None:
    """Gateway exceptions propagate without being wrapped."""
    adapter, gateway, _ = _make_adapter()
    gateway.call.side_effect = RuntimeError("model error")
    low_conf = _textract_result_with_confidence(50.0)

    with patch(_PYMUPDF_PATH, return_value=_empty_pymupdf()):
        with patch.object(adapter, "_build_image_content", return_value=[]):
            with pytest.raises(RuntimeError, match="model error"):
                adapter.extract(_make_upload(), _DOC_ID, low_conf)
