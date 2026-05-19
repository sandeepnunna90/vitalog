"""AWS Textract adapter — primary OCR path (ADR-02).

Calls AnalyzeDocument(FeatureTypes=[FORMS, TABLES]) synchronously,
normalizes the response into our Pydantic schema, and writes an audit entry.
Retries transient AWS errors with exponential backoff (max 3 attempts).
"""

from __future__ import annotations

import os
import time
import uuid
from typing import Any

from src._retry import ADAPTER_RETRY_SLEEP
from src.ingestion.errors import TextractFailureError
from src.ingestion.textract_schemas import (
    Block,
    BoundingBox,
    KVPair,
    Table,
    TableCell,
    TextractResult,
)
from src.ingestion.upload_validator import ValidatedUpload
from src.persistence.audit_log_repository import AuditLogRepository

_RETRYABLE_ERROR_CODES: frozenset[str] = frozenset(
    {
        "ProvisionedThroughputExceededException",
        "ThrottlingException",
        "InternalServerError",
        "ServiceUnavailableException",
    }
)


class TextractAdapter:
    def __init__(
        self,
        audit_repo: AuditLogRepository,
        region: str | None = None,
        max_retries: int = 3,
        client: Any | None = None,
    ) -> None:
        if client is not None:
            self._client = client
        else:
            import boto3

            self._client = boto3.client(
                "textract",
                region_name=region or os.getenv("AWS_REGION", "us-east-1"),
            )
        self._audit = audit_repo
        # Clamp so ADAPTER_RETRY_SLEEP[attempt] never goes out of bounds.
        self._max_retries = min(max_retries, len(ADAPTER_RETRY_SLEEP))

    def extract(self, upload: ValidatedUpload, document_id: uuid.UUID) -> TextractResult:
        start = time.monotonic()
        raw = self._call_textract(upload.file_bytes)
        latency_ms = int((time.monotonic() - start) * 1000)
        result = self._normalize(raw)

        all_confs: list[float] = (
            [b.confidence for b in result.blocks]
            + [c.confidence for t in result.tables for row in t.rows for c in row]
            + [kv.key_confidence for kv in result.kv_pairs]
            + [kv.value_confidence for kv in result.kv_pairs]
        )
        self._audit.record(
            "system",
            "textract_extracted",
            {
                "document_id": str(document_id),
                "latency_ms": latency_ms,
                "min_confidence": min(all_confs, default=0.0),
                "max_confidence": max(all_confs, default=0.0),
                "table_count": len(result.tables),
                "kv_count": len(result.kv_pairs),
            },
        )
        return result

    def _call_textract(self, file_bytes: bytes) -> dict[str, Any]:
        import botocore.exceptions

        last_exc: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                return self._client.analyze_document(  # type: ignore[no-any-return]
                    Document={"Bytes": file_bytes},
                    FeatureTypes=["FORMS", "TABLES"],
                )
            except botocore.exceptions.NoCredentialsError as exc:
                # Config error — not transient; fail immediately
                raise TextractFailureError(str(exc), attempt + 1) from exc
            except botocore.exceptions.ClientError as exc:
                code = exc.response["Error"]["Code"]
                if code not in _RETRYABLE_ERROR_CODES:
                    raise TextractFailureError(str(exc), attempt + 1) from exc
                last_exc = exc
            except botocore.exceptions.BotoCoreError as exc:
                last_exc = exc
            if attempt < self._max_retries - 1:
                time.sleep(ADAPTER_RETRY_SLEEP[attempt])
        raise TextractFailureError(str(last_exc), self._max_retries) from last_exc

    def _normalize(self, raw: dict[str, Any]) -> TextractResult:
        blocks_raw: list[dict[str, Any]] = raw.get("Blocks", [])

        # Build id → raw block index for relationship traversal
        by_id: dict[str, dict[str, Any]] = {b["Id"]: b for b in blocks_raw}

        line_blocks: list[Block] = []
        tables: list[Table] = []
        kv_pairs: list[KVPair] = []
        page_count = 0

        for blk in blocks_raw:
            btype = blk.get("BlockType", "")

            if btype == "PAGE":
                page_count += 1

            elif btype == "LINE":
                line_blocks.append(
                    Block(
                        block_id=blk["Id"],
                        text=blk.get("Text", ""),
                        confidence=blk.get("Confidence", 0.0),
                        bbox=_bbox(blk),
                    )
                )

            elif btype == "TABLE":
                cell_ids = _child_ids(blk)
                cell_map: dict[tuple[int, int], TableCell] = {}
                for cid in cell_ids:
                    cell_blk = by_id.get(cid)
                    if cell_blk is None or cell_blk.get("BlockType") != "CELL":
                        continue
                    row_idx = cell_blk.get("RowIndex", 1)
                    col_idx = cell_blk.get("ColumnIndex", 1)
                    word_ids = _child_ids(cell_blk)
                    cell_text = " ".join(
                        by_id[wid].get("Text", "")
                        for wid in word_ids
                        if wid in by_id and by_id[wid].get("BlockType") == "WORD"
                    )
                    # Known capstone limitation: if Textract returns cells with the
                    # same (RowIndex, ColumnIndex) — e.g. merged/spanning cells —
                    # the later block silently overwrites the earlier one. RowSpan
                    # and ColumnSpan are not handled. Lab-report tables rarely use
                    # merged cells; fix in post-capstone if needed.
                    cell_map[(row_idx, col_idx)] = TableCell(
                        row_index=row_idx,
                        col_index=col_idx,
                        text=cell_text,
                        confidence=cell_blk.get("Confidence", 0.0),
                        bbox=_bbox(cell_blk),
                    )
                rows = _to_row_matrix(cell_map)
                tables.append(
                    Table(
                        table_id=blk["Id"],
                        rows=rows,
                        confidence=blk.get("Confidence", 0.0),
                    )
                )

            elif btype == "KEY_VALUE_SET":
                entity_types: list[str] = blk.get("EntityTypes", [])
                if "KEY" not in entity_types:
                    continue
                key_text = _assemble_text(blk, by_id)
                key_conf = blk.get("Confidence", 0.0)
                key_box = _bbox(blk)

                value_blk: dict[str, Any] | None = None
                for rel in blk.get("Relationships", []):
                    if rel.get("Type") == "VALUE":
                        for vid in rel.get("Ids", []):
                            value_blk = by_id.get(vid)
                            break
                    if value_blk is not None:
                        break

                if value_blk is None:
                    continue
                value_text = _assemble_text(value_blk, by_id)
                value_conf = value_blk.get("Confidence", 0.0)

                kv_pairs.append(
                    KVPair(
                        key=key_text,
                        value=value_text,
                        key_confidence=key_conf,
                        value_confidence=value_conf,
                        bbox=key_box,
                    )
                )

        return TextractResult(
            blocks=line_blocks,
            tables=tables,
            kv_pairs=kv_pairs,
            page_count=page_count,
        )


# ── Helpers ───────────────────────────────────────────────────────────────────


def _bbox(blk: dict[str, Any]) -> BoundingBox | None:
    geo = blk.get("Geometry", {}).get("BoundingBox")
    if geo is None:
        return None
    return BoundingBox(
        left=geo.get("Left", 0.0),
        top=geo.get("Top", 0.0),
        width=geo.get("Width", 0.0),
        height=geo.get("Height", 0.0),
    )


def _child_ids(blk: dict[str, Any]) -> list[str]:
    for rel in blk.get("Relationships", []):
        if rel.get("Type") == "CHILD":
            ids: list[str] = rel.get("Ids", [])
            return ids
    return []


def _assemble_text(blk: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> str:
    """Join WORD children of a KEY_VALUE_SET or CELL block into a text string."""
    word_ids = _child_ids(blk)
    return " ".join(
        by_id[wid].get("Text", "")
        for wid in word_ids
        if wid in by_id and by_id[wid].get("BlockType") == "WORD"
    )


def _to_row_matrix(cell_map: dict[tuple[int, int], TableCell]) -> list[list[TableCell]]:
    if not cell_map:
        return []
    max_row = max(r for r, _ in cell_map)
    max_col = max(c for _, c in cell_map)
    rows: list[list[TableCell]] = []
    for r in range(1, max_row + 1):
        row: list[TableCell] = []
        for c in range(1, max_col + 1):
            cell = cell_map.get((r, c))
            if cell is not None:
                row.append(cell)
        if row:
            rows.append(row)
    return rows
