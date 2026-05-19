"""Unit tests for the Structurer (D6).

Gateway and AuditLogRepository are mocked — no real LLM calls or Supabase writes.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from src.ingestion.structurer import (
    THRESHOLD_AUTO_ACCEPT,
    THRESHOLD_REJECT,
    Structurer,
    _compute_textract_floor,
    _serialize_textract_result,
)
from src.ingestion.structurer_schemas import (
    Band,
    RawBiomarkerCandidate,
    StructuredReport,
)
from src.ingestion.textract_schemas import Block, KVPair, Table, TableCell, TextractResult

# ── Constants ─────────────────────────────────────────────────────────────────

_DOC_ID = uuid.UUID("00000000-0000-0000-0000-000000000006")
_HIGH_CLASS_CONF = 0.95  # → 95.0 after scaling
_MID_CLASS_CONF = 0.80  # → 80.0 after scaling
_LOW_CLASS_CONF = 0.50  # → 50.0 after scaling — always below minimum grid THRESHOLD_REJECT (60)


# ── Fixtures ──────────────────────────────────────────────────────────────────


def _make_structurer() -> tuple[Structurer, MagicMock, MagicMock]:
    gateway = MagicMock()
    audit = MagicMock()
    return Structurer(gateway=gateway, audit_repo=audit), gateway, audit


def _high_confidence_textract() -> TextractResult:
    return TextractResult(
        blocks=[Block(block_id="b1", text="HbA1c 6.1 %", confidence=98.0, bbox=None)],
        tables=[],
        kv_pairs=[
            KVPair(key="HbA1c", value="6.1", key_confidence=98.0, value_confidence=97.0, bbox=None)
        ],
        page_count=1,
    )


def _make_raw_candidate(
    name: str = "HbA1c",
    value: str = "6.1",
    unit: str = "%",
    llm_confidence: float = 96.0,
) -> RawBiomarkerCandidate:
    return RawBiomarkerCandidate(
        raw_name=name,
        raw_value=value,
        raw_unit=unit,
        raw_reference_range="4.0-5.6",
        collection_date="2024-03-15",
        lab_source="Quest Diagnostics",
        llm_confidence=llm_confidence,
        source_page=1,
    )


def _make_structured_report(
    candidates: list[RawBiomarkerCandidate] | None = None,
    notes: str = "",
) -> StructuredReport:
    return StructuredReport(
        candidates=candidates or [_make_raw_candidate()],
        extraction_notes=notes,
    )


# ── Named constants exposed at module level ───────────────────────────────────


def test_threshold_constants_defined() -> None:
    """THRESHOLD_AUTO_ACCEPT and THRESHOLD_REJECT are valid named module-level constants."""
    assert isinstance(THRESHOLD_AUTO_ACCEPT, float)
    assert isinstance(THRESHOLD_REJECT, float)
    assert THRESHOLD_REJECT < THRESHOLD_AUTO_ACCEPT


# ── Auto-accept band ──────────────────────────────────────────────────────────


def test_structure_returns_auto_accept_candidates() -> None:
    """High textract + high llm + high classification → all auto_accept."""
    structurer, gateway, _ = _make_structurer()
    gateway.call.return_value = _make_structured_report([_make_raw_candidate(llm_confidence=96.0)])
    result = structurer.structure(_high_confidence_textract(), _DOC_ID, _HIGH_CLASS_CONF)

    assert len(result.candidates) == 1
    assert result.candidates[0].band == Band.AUTO_ACCEPT
    assert result.has_rejects is False


# ── Review band ───────────────────────────────────────────────────────────────


def test_structure_returns_review_candidates() -> None:
    """Mid llm_confidence drives composite below auto-accept threshold → review."""
    structurer, gateway, _ = _make_structurer()
    # textract_floor=97, llm=75, class=95 → composite=75 → REVIEW
    gateway.call.return_value = _make_structured_report([_make_raw_candidate(llm_confidence=75.0)])
    result = structurer.structure(_high_confidence_textract(), _DOC_ID, _HIGH_CLASS_CONF)

    assert result.candidates[0].band == Band.REVIEW
    assert result.has_rejects is False


# ── Reject band ───────────────────────────────────────────────────────────────


def test_structure_returns_reject_candidates() -> None:
    """Low llm_confidence → reject band, has_rejects=True."""
    structurer, gateway, _ = _make_structurer()
    # textract_floor=97, llm=30, class=95 → composite=30 → REJECT
    gateway.call.return_value = _make_structured_report([_make_raw_candidate(llm_confidence=30.0)])
    result = structurer.structure(_high_confidence_textract(), _DOC_ID, _HIGH_CLASS_CONF)

    assert result.candidates[0].band == Band.REJECT
    assert result.has_rejects is True


def test_has_rejects_false_when_all_above_threshold() -> None:
    structurer, gateway, _ = _make_structurer()
    gateway.call.return_value = _make_structured_report(
        [
            _make_raw_candidate(llm_confidence=96.0),
            _make_raw_candidate(name="Glucose", llm_confidence=95.0),
        ]
    )
    result = structurer.structure(_high_confidence_textract(), _DOC_ID, _HIGH_CLASS_CONF)

    assert result.has_rejects is False


# ── Empty document ────────────────────────────────────────────────────────────


def test_empty_textract_triggers_empty_result() -> None:
    """Empty TextractResult → gateway called with '(empty document)', 0 candidates returned."""
    structurer, gateway, _ = _make_structurer()
    gateway.call.return_value = StructuredReport(candidates=[], extraction_notes="no text")
    empty = TextractResult(blocks=[], tables=[], kv_pairs=[], page_count=0)

    result = structurer.structure(empty, _DOC_ID, _HIGH_CLASS_CONF)

    assert result.candidates == []
    assert result.has_rejects is False
    call_kwargs = gateway.call.call_args
    assert call_kwargs[1]["inputs"]["document_text"] == "(empty document)"


# ── Composite confidence on the candidate ─────────────────────────────────────


def test_composite_confidence_stored_on_candidate() -> None:
    """BiomarkerCandidate.composite_confidence equals min(textract, llm, class*100)."""
    structurer, gateway, _ = _make_structurer()
    # textract_floor = 97 (min of 98, 98, 97); llm=80; class=0.95 → 95
    # composite = min(97, 80, 95) = 80
    gateway.call.return_value = _make_structured_report([_make_raw_candidate(llm_confidence=80.0)])
    result = structurer.structure(_high_confidence_textract(), _DOC_ID, _HIGH_CLASS_CONF)

    assert result.candidates[0].composite_confidence == 80.0


def test_classification_confidence_drives_composite_floor() -> None:
    """When classification_confidence is lowest, it sets the composite floor end-to-end."""
    structurer, gateway, _ = _make_structurer()
    # textract_floor=97, llm=96, class=_LOW_CLASS_CONF=0.50 → 50.0
    # composite = min(97, 96, 50) = 50 → REJECT band (50 < THRESHOLD_REJECT for any grid value)
    gateway.call.return_value = _make_structured_report([_make_raw_candidate(llm_confidence=96.0)])
    result = structurer.structure(_high_confidence_textract(), _DOC_ID, _LOW_CLASS_CONF)

    assert result.candidates[0].composite_confidence == 50.0
    assert result.candidates[0].band == Band.REJECT


def test_mid_classification_confidence_does_not_force_reject() -> None:
    """classification_confidence=0.80 → 80.0 → stays in REVIEW when LLM is also mid."""
    structurer, gateway, _ = _make_structurer()
    # textract_floor=97, llm=96, class=_MID_CLASS_CONF=0.80 → 80.0
    # composite = min(97, 96, 80) = 80 → REVIEW band (not REJECT)
    gateway.call.return_value = _make_structured_report([_make_raw_candidate(llm_confidence=96.0)])
    result = structurer.structure(_high_confidence_textract(), _DOC_ID, _MID_CLASS_CONF)

    assert result.candidates[0].composite_confidence == 80.0
    assert result.candidates[0].band == Band.REVIEW


# ── Audit log ─────────────────────────────────────────────────────────────────


def test_audit_record_written_after_structure() -> None:
    structurer, gateway, audit = _make_structurer()
    gateway.call.return_value = _make_structured_report()
    structurer.structure(_high_confidence_textract(), _DOC_ID, _HIGH_CLASS_CONF)

    audit.record.assert_called_once()
    args = audit.record.call_args[0]
    assert args[1] == "structurer_complete"
    payload = args[2]
    assert payload["document_id"] == str(_DOC_ID)
    assert "candidate_count" in payload
    assert "has_rejects" in payload


# ── Error propagation ─────────────────────────────────────────────────────────


def test_gateway_error_propagates() -> None:
    structurer, gateway, _ = _make_structurer()
    gateway.call.side_effect = RuntimeError("model error")

    with pytest.raises(RuntimeError, match="model error"):
        structurer.structure(_high_confidence_textract(), _DOC_ID, _HIGH_CLASS_CONF)


# ── _serialize_textract_result ────────────────────────────────────────────────


def test_serialize_empty_result() -> None:
    empty = TextractResult(blocks=[], tables=[], kv_pairs=[], page_count=0)
    assert _serialize_textract_result(empty) == "(empty document)"


def test_serialize_kv_pairs() -> None:
    result = TextractResult(
        blocks=[],
        tables=[],
        kv_pairs=[
            KVPair(key="HbA1c", value="6.1%", key_confidence=98.0, value_confidence=97.0, bbox=None)
        ],
        page_count=1,
    )
    text = _serialize_textract_result(result)
    assert "KEY-VALUE PAIRS:" in text
    assert "HbA1c: 6.1%" in text


def test_serialize_table() -> None:
    result = TextractResult(
        blocks=[],
        tables=[
            Table(
                table_id="t1",
                rows=[
                    [
                        TableCell(
                            row_index=1, col_index=1, text="Test", confidence=95.0, bbox=None
                        ),
                        TableCell(
                            row_index=1, col_index=2, text="Value", confidence=95.0, bbox=None
                        ),
                    ]
                ],
                confidence=95.0,
            )
        ],
        kv_pairs=[],
        page_count=1,
    )
    text = _serialize_textract_result(result)
    assert "TABLES:" in text
    assert "Test | Value" in text


def test_serialize_blocks() -> None:
    result = TextractResult(
        blocks=[Block(block_id="b1", text="Patient: Mark", confidence=99.0, bbox=None)],
        tables=[],
        kv_pairs=[],
        page_count=1,
    )
    text = _serialize_textract_result(result)
    assert "TEXT LINES:" in text
    assert "Patient: Mark" in text


# ── _compute_textract_floor ────────────────────────────────────────────────────


def test_textract_floor_uses_minimum_across_all_field_types() -> None:
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
    assert _compute_textract_floor(result) == 55.0


def test_textract_floor_empty_returns_zero() -> None:
    empty = TextractResult(blocks=[], tables=[], kv_pairs=[], page_count=0)
    assert _compute_textract_floor(empty) == 0.0
