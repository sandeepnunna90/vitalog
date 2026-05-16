"""Unit tests for TextractAdapter.

boto3 client is injected via client= parameter so no real AWS calls are made.
All Textract response fixtures are inline dicts — no committed binary files.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest

from src.ingestion.errors import TextractFailureError
from src.ingestion.textract_adapter import TextractAdapter
from src.ingestion.textract_schemas import TextractResult
from src.ingestion.upload_validator import ValidatedUpload

# ── Shared constants ──────────────────────────────────────────────────────────

_DOCUMENT_ID = uuid.UUID("00000000-0000-0000-0000-000000000042")
_FILE_BYTES = b"fake pdf content"


# ── Fixtures ──────────────────────────────────────────────────────────────────


def _make_upload(mime: str = "application/pdf") -> ValidatedUpload:
    return ValidatedUpload(
        file_bytes=_FILE_BYTES,
        mime=mime,
        size_bytes=len(_FILE_BYTES),
        is_text_extractable=True,
        resolution_warning=None,
    )


def _make_adapter(client: MagicMock) -> tuple[TextractAdapter, MagicMock]:
    audit = MagicMock()
    adapter = TextractAdapter(audit_repo=audit, client=client)
    return adapter, audit


def _minimal_response(extra_blocks: list[dict] | None = None) -> dict:
    """Minimal valid Textract AnalyzeDocument response."""
    blocks: list[dict] = [
        {
            "Id": "page-1",
            "BlockType": "PAGE",
            "Page": 1,
        }
    ]
    if extra_blocks:
        blocks.extend(extra_blocks)
    return {"Blocks": blocks, "DocumentMetadata": {"Pages": 1}}


def _make_client_error(code: str) -> Exception:
    import botocore.exceptions

    return botocore.exceptions.ClientError(
        {"Error": {"Code": code, "Message": "test error"}},
        "AnalyzeDocument",
    )


# ── Basic extraction tests ────────────────────────────────────────────────────


def test_extract_returns_textract_result() -> None:
    client = MagicMock()
    client.analyze_document.return_value = _minimal_response()
    adapter, _ = _make_adapter(client)

    result = adapter.extract(_make_upload(), _DOCUMENT_ID)

    assert isinstance(result, TextractResult)


def test_line_blocks_normalized() -> None:
    line_block = {
        "Id": "line-1",
        "BlockType": "LINE",
        "Text": "Glucose 95 mg/dL",
        "Confidence": 99.1,
        "Geometry": {"BoundingBox": {"Left": 0.1, "Top": 0.2, "Width": 0.5, "Height": 0.03}},
    }
    client = MagicMock()
    client.analyze_document.return_value = _minimal_response([line_block])
    adapter, _ = _make_adapter(client)

    result = adapter.extract(_make_upload(), _DOCUMENT_ID)

    assert len(result.blocks) == 1
    blk = result.blocks[0]
    assert blk.block_id == "line-1"
    assert blk.text == "Glucose 95 mg/dL"
    assert blk.confidence == pytest.approx(99.1)
    assert blk.bbox is not None
    assert blk.bbox.left == pytest.approx(0.1)


def test_table_reconstructed_row_major() -> None:
    word_id = "word-1"
    cell_id = "cell-1"
    table_id = "table-1"
    blocks = [
        {
            "Id": word_id,
            "BlockType": "WORD",
            "Text": "HbA1c",
        },
        {
            "Id": cell_id,
            "BlockType": "CELL",
            "RowIndex": 1,
            "ColumnIndex": 1,
            "Confidence": 97.5,
            "Geometry": {"BoundingBox": {"Left": 0.0, "Top": 0.0, "Width": 0.2, "Height": 0.05}},
            "Relationships": [{"Type": "CHILD", "Ids": [word_id]}],
        },
        {
            "Id": table_id,
            "BlockType": "TABLE",
            "Confidence": 98.0,
            "Relationships": [{"Type": "CHILD", "Ids": [cell_id]}],
        },
    ]
    client = MagicMock()
    client.analyze_document.return_value = _minimal_response(blocks)
    adapter, _ = _make_adapter(client)

    result = adapter.extract(_make_upload(), _DOCUMENT_ID)

    assert len(result.tables) == 1
    tbl = result.tables[0]
    assert tbl.table_id == table_id
    assert tbl.confidence == pytest.approx(98.0)
    assert len(tbl.rows) == 1
    cell = tbl.rows[0][0]
    assert cell.row_index == 1
    assert cell.col_index == 1
    assert cell.text == "HbA1c"
    assert cell.confidence == pytest.approx(97.5)


def test_kv_pairs_resolved() -> None:
    key_word_id = "kw-1"
    val_word_id = "vw-1"
    key_block_id = "key-1"
    val_block_id = "val-1"
    blocks = [
        {"Id": key_word_id, "BlockType": "WORD", "Text": "Glucose"},
        {"Id": val_word_id, "BlockType": "WORD", "Text": "95"},
        {
            "Id": val_block_id,
            "BlockType": "KEY_VALUE_SET",
            "EntityTypes": ["VALUE"],
            "Confidence": 91.0,
            "Relationships": [{"Type": "CHILD", "Ids": [val_word_id]}],
        },
        {
            "Id": key_block_id,
            "BlockType": "KEY_VALUE_SET",
            "EntityTypes": ["KEY"],
            "Confidence": 96.0,
            "Geometry": {"BoundingBox": {"Left": 0.1, "Top": 0.3, "Width": 0.2, "Height": 0.02}},
            "Relationships": [
                {"Type": "CHILD", "Ids": [key_word_id]},
                {"Type": "VALUE", "Ids": [val_block_id]},
            ],
        },
    ]
    client = MagicMock()
    client.analyze_document.return_value = _minimal_response(blocks)
    adapter, _ = _make_adapter(client)

    result = adapter.extract(_make_upload(), _DOCUMENT_ID)

    assert len(result.kv_pairs) == 1
    kv = result.kv_pairs[0]
    assert kv.key == "Glucose"
    assert kv.value == "95"
    assert kv.key_confidence == pytest.approx(96.0)
    assert kv.value_confidence == pytest.approx(91.0)
    assert kv.bbox is not None


def test_page_count_from_page_blocks() -> None:
    extra = [{"Id": "page-2", "BlockType": "PAGE", "Page": 2}]
    client = MagicMock()
    client.analyze_document.return_value = _minimal_response(extra)
    adapter, _ = _make_adapter(client)

    result = adapter.extract(_make_upload(), _DOCUMENT_ID)

    assert result.page_count == 2  # one PAGE from _minimal_response + one extra


def test_image_bytes_dispatched() -> None:
    """Image uploads dispatch to analyze_document with Bytes field (AC4)."""
    client = MagicMock()
    client.analyze_document.return_value = _minimal_response()
    adapter, _ = _make_adapter(client)

    adapter.extract(_make_upload(mime="image/jpeg"), _DOCUMENT_ID)

    call_kwargs = client.analyze_document.call_args.kwargs
    assert call_kwargs["Document"] == {"Bytes": _FILE_BYTES}
    assert "FORMS" in call_kwargs["FeatureTypes"]
    assert "TABLES" in call_kwargs["FeatureTypes"]


# ── Audit tests ───────────────────────────────────────────────────────────────


def test_audit_event_type() -> None:
    client = MagicMock()
    client.analyze_document.return_value = _minimal_response()
    adapter, audit = _make_adapter(client)

    adapter.extract(_make_upload(), _DOCUMENT_ID)

    _, event_type, _ = audit.record.call_args.args
    assert event_type == "textract_extracted"


def test_audit_fields_written() -> None:
    line_block = {
        "Id": "line-1",
        "BlockType": "LINE",
        "Text": "Test",
        "Confidence": 88.0,
    }
    client = MagicMock()
    client.analyze_document.return_value = _minimal_response([line_block])
    adapter, audit = _make_adapter(client)

    adapter.extract(_make_upload(), _DOCUMENT_ID)

    _, _, payload = audit.record.call_args.args
    assert payload["document_id"] == str(_DOCUMENT_ID)
    assert isinstance(payload["latency_ms"], int)
    assert payload["min_confidence"] == pytest.approx(88.0)
    assert payload["max_confidence"] == pytest.approx(88.0)
    assert payload["table_count"] == 0
    assert payload["kv_count"] == 0


# ── Retry and error tests ─────────────────────────────────────────────────────


def test_retry_on_throttling() -> None:
    """ThrottlingException on first two calls, success on third (AC5)."""
    client = MagicMock()
    throttle_err = _make_client_error("ThrottlingException")
    client.analyze_document.side_effect = [
        throttle_err,
        throttle_err,
        _minimal_response(),
    ]
    adapter, audit = _make_adapter(client)

    with patch("time.sleep"):
        result = adapter.extract(_make_upload(), _DOCUMENT_ID)

    assert isinstance(result, TextractResult)
    assert client.analyze_document.call_count == 3
    audit.record.assert_called_once()


def test_exhausted_retries_raises_textract_failure_error() -> None:
    """All 3 attempts fail → TextractFailureError raised (AC5)."""
    client = MagicMock()
    throttle_err = _make_client_error("ProvisionedThroughputExceededException")
    client.analyze_document.side_effect = throttle_err

    adapter, audit = _make_adapter(client)

    with patch("time.sleep"), pytest.raises(TextractFailureError) as exc_info:
        adapter.extract(_make_upload(), _DOCUMENT_ID)

    assert exc_info.value.attempt_count == 3
    audit.record.assert_not_called()


def test_non_retryable_client_error_raises_immediately() -> None:
    """InvalidParameterException → TextractFailureError on first attempt, no retry (AC5)."""
    client = MagicMock()
    client.analyze_document.side_effect = _make_client_error("InvalidParameterException")
    adapter, audit = _make_adapter(client)

    with pytest.raises(TextractFailureError) as exc_info:
        adapter.extract(_make_upload(), _DOCUMENT_ID)

    assert client.analyze_document.call_count == 1
    assert exc_info.value.attempt_count == 1
    audit.record.assert_not_called()


# ── Integration test ──────────────────────────────────────────────────────────


@pytest.mark.integration
def test_integration_real_textract(text_pdf_bytes: bytes) -> None:
    """Calls real AWS Textract. Requires valid creds in .env. Skipped in CI."""
    import os

    from src.persistence.audit_log_repository import AuditLogRepository

    if not os.getenv("AWS_ACCESS_KEY_ID"):
        pytest.skip("AWS_ACCESS_KEY_ID not set — skipping real Textract call")

    audit = MagicMock(spec=AuditLogRepository)
    adapter = TextractAdapter(audit_repo=audit)

    upload = ValidatedUpload(
        file_bytes=text_pdf_bytes,
        mime="application/pdf",
        size_bytes=len(text_pdf_bytes),
        is_text_extractable=True,
        resolution_warning=None,
    )
    result = adapter.extract(upload, _DOCUMENT_ID)

    assert isinstance(result, TextractResult)
    assert result.page_count >= 1
    audit.record.assert_called_once()
