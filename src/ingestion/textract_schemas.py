"""Pydantic models for normalized AWS Textract output.

Downstream services (structurer, D6) consume these types exclusively —
raw boto3 response dicts never leak past TextractAdapter._normalize().
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class BoundingBox(BaseModel):
    model_config = ConfigDict(strict=True)

    left: float
    top: float
    width: float
    height: float


class Block(BaseModel):
    """One LINE block from Textract — a single line of recognized text."""

    model_config = ConfigDict(strict=True)

    block_id: str
    text: str
    confidence: float  # Textract-native 0–100 scale
    bbox: BoundingBox | None


class TableCell(BaseModel):
    model_config = ConfigDict(strict=True)

    row_index: int  # 1-based (Textract native)
    col_index: int
    text: str
    confidence: float
    bbox: BoundingBox | None


class Table(BaseModel):
    model_config = ConfigDict(strict=True)

    table_id: str
    rows: list[list[TableCell]]  # row-major; outer index = row, inner = cell
    confidence: float  # TABLE-block-level confidence


class KVPair(BaseModel):
    model_config = ConfigDict(strict=True)

    key: str
    value: str
    key_confidence: float
    value_confidence: float
    bbox: BoundingBox | None  # KEY block bounding box


class TextractResult(BaseModel):
    model_config = ConfigDict(strict=True)

    blocks: list[Block]  # LINE blocks — one entry per recognized text line
    tables: list[Table]
    kv_pairs: list[KVPair]
    page_count: int
