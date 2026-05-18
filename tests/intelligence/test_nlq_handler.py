"""Unit tests for NlqHandler (F3 ACs 1–6)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from src.intelligence.nlq_handler import _SAFE_REFUSAL, NlqHandler
from src.intelligence.nlq_schemas import NlqResponse
from src.persistence.biomarker_repository import BiomarkerRepository
from src.persistence.models import BiomarkerRecordRow

_PROJECT_ROOT = Path(__file__).parent.parent.parent
_PROMPTS_DIR = _PROJECT_ROOT / "prompts"
_PATIENT_ID = uuid.uuid4()
_RECORD_ID = uuid.uuid4()

_GOOD_RAW: dict[str, Any] = {
    "text": "Your most recent HbA1c result was 6.8% on March 12, 2026.",
}

# 9.9 is not in the retrieval set (record has 6.8) → Mode B rejects
_BAD_RAW: dict[str, Any] = {
    "text": "Your HbA1c was 9.9%, which is above average.",
}


def _make_record(**kwargs: Any) -> BiomarkerRecordRow:
    defaults: dict[str, Any] = {
        "record_id": _RECORD_ID,
        "patient_id": _PATIENT_ID,
        "document_id": None,
        "canonical_biomarker_id": "hba1c",
        "pending_taxonomy_id": None,
        "original_name": "HbA1c",
        "original_value": "6.8",
        "original_unit": "%",
        "original_range": None,
        "canonical_value": 6.8,
        "canonical_unit": "%",
        "collection_date": date(2026, 3, 12),
        "lab_source": "Quest Diagnostics",
        "extraction_confidence": 98.0,
        "verified_by": "auto",
        "created_at": datetime(2026, 3, 12, 10, 0, 0),
    }
    defaults.update(kwargs)
    return BiomarkerRecordRow.model_validate(defaults)


def _make_handler(
    records: list[BiomarkerRecordRow] | None = None,
    audit_repo: Any = None,
) -> NlqHandler:
    repo = MagicMock(spec=BiomarkerRepository)
    repo.find_by_canonical_id.return_value = records if records is not None else [_make_record()]

    from src.gateway.gateway import Gateway

    gw = Gateway(prompts_dir=_PROMPTS_DIR)
    return NlqHandler(gateway=gw, biomarker_repo=repo, audit_repo=audit_repo)


# ── AC1: happy path structure ─────────────────────────────────────────────────


def test_answer_returns_nlq_response_structure() -> None:
    """AC1: answer() returns an NlqResponse with correct field types."""
    handler = _make_handler()
    with patch(
        "src.gateway.anthropic_adapter.AnthropicAdapter.call",
        return_value=(_GOOD_RAW, 50, 20),
    ):
        resp = handler.answer("what's my HbA1c?", _PATIENT_ID)

    assert isinstance(resp, NlqResponse)
    assert isinstance(resp.text, str)
    assert len(resp.text) > 0
    assert isinstance(resp.retrieval_count, int)
    assert isinstance(resp.is_fallback, bool)


def test_answer_is_not_fallback_on_success() -> None:
    """AC1: successful LLM answer → is_fallback=False, retrieval_count > 0."""
    handler = _make_handler()
    with patch(
        "src.gateway.anthropic_adapter.AnthropicAdapter.call",
        return_value=(_GOOD_RAW, 50, 20),
    ):
        resp = handler.answer("what's my HbA1c?", _PATIENT_ID)

    assert resp.is_fallback is False
    assert resp.retrieval_count > 0


# ── AC6: prompt version ───────────────────────────────────────────────────────


def test_answer_prompt_version_is_v1() -> None:
    """AC6: prompt_version field must equal 'v1'."""
    handler = _make_handler()
    with patch(
        "src.gateway.anthropic_adapter.AnthropicAdapter.call",
        return_value=(_GOOD_RAW, 50, 20),
    ):
        resp = handler.answer("what's my HbA1c?", _PATIENT_ID)

    assert resp.prompt_version == "v1"


# ── AC2: graceful fallback when biomarker recognized but no records ───────────


def test_answer_missing_biomarker_graceful_fallback() -> None:
    """AC2: biomarker recognized (TSH via alias) but no records → is_fallback=True, no LLM."""
    handler = _make_handler(records=[])  # repo returns empty for every canonical ID

    # AnthropicAdapter.call must NOT be called (fallback is templated)
    with patch(
        "src.gateway.anthropic_adapter.AnthropicAdapter.call",
    ) as mock_call:
        resp = handler.answer("what's my TSH?", _PATIENT_ID)
        mock_call.assert_not_called()

    assert resp.is_fallback is True
    assert resp.retrieval_count == 0
    assert "Upload" in resp.text


def test_answer_missing_biomarker_with_condition_expansion_appends_disclaimer() -> None:
    """Condition expansion fires but all records missing → fallback text + condition disclaimer."""
    handler = _make_handler(records=[])  # all biomarker lookups return empty

    with patch("src.gateway.anthropic_adapter.AnthropicAdapter.call") as mock_call:
        # "diabetes" triggers T2D condition expansion; repo returns nothing for any biomarker
        resp = handler.answer("show me my diabetes markers", _PATIENT_ID)
        mock_call.assert_not_called()

    assert resp.is_fallback is True
    assert resp.retrieval_count == 0
    # Condition disclaimer must be appended even on the missing-records path
    assert "clinical guidelines" in resp.text
    assert len(resp.matched_condition_names) > 0


def test_answer_matched_condition_names_exposed_on_response() -> None:
    """matched_condition_names is populated on NlqResponse when condition expansion fired."""
    handler = _make_handler()

    with patch(
        "src.gateway.anthropic_adapter.AnthropicAdapter.call",
        return_value=(_GOOD_RAW, 50, 20),
    ):
        # "diabetes" expands T2D; hba1c record is present so LLM fires
        resp = handler.answer("show me my diabetes results", _PATIENT_ID)

    assert isinstance(resp.matched_condition_names, list)
    # Condition expansion fired — at least one condition name must be present
    assert len(resp.matched_condition_names) > 0


def test_answer_matched_condition_names_empty_for_direct_alias() -> None:
    """matched_condition_names is empty when query resolved via direct alias only."""
    handler = _make_handler()

    with patch(
        "src.gateway.anthropic_adapter.AnthropicAdapter.call",
        return_value=(_GOOD_RAW, 50, 20),
    ):
        resp = handler.answer("what's my HbA1c?", _PATIENT_ID)

    assert resp.matched_condition_names == []


# ── AC4: safe refusal for unrecognized queries ────────────────────────────────


def test_answer_unrecognized_query_safe_refusal() -> None:
    """AC4: query with no recognized biomarker or condition → safe-refusal text."""
    handler = _make_handler()

    with patch(
        "src.gateway.anthropic_adapter.AnthropicAdapter.call",
    ) as mock_call:
        resp = handler.answer("what is the weather today?", _PATIENT_ID)
        mock_call.assert_not_called()

    assert resp.text == _SAFE_REFUSAL
    assert resp.retrieval_count == 0
    assert resp.is_fallback is True


# ── AC3: Mode B rejection → safe refusal ─────────────────────────────────────


def test_answer_mode_b_rejects_hallucinated_value() -> None:
    """AC3: both attempts return a Mode B-rejected value → safe-refusal text."""
    handler = _make_handler()
    with patch(
        "src.gateway.anthropic_adapter.AnthropicAdapter.call",
        return_value=(_BAD_RAW, 50, 20),
    ):
        resp = handler.answer("what's my HbA1c?", _PATIENT_ID)

    assert resp.text == _SAFE_REFUSAL
    assert resp.is_fallback is True


def test_answer_mode_b_retry_succeeds() -> None:
    """AC3/AC6: first attempt fails Mode B; second attempt returns valid output."""
    handler = _make_handler()
    call_count = 0

    def _side_effect(*_args: Any, **_kwargs: Any) -> tuple[dict[str, Any], int, int]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return (_BAD_RAW, 50, 20)
        return (_GOOD_RAW, 50, 20)

    with patch(
        "src.gateway.anthropic_adapter.AnthropicAdapter.call",
        side_effect=_side_effect,
    ):
        resp = handler.answer("what's my HbA1c?", _PATIENT_ID)

    assert resp.is_fallback is False
    assert call_count == 2


# ── Partial retrieval: some found, some missing ───────────────────────────────


def test_answer_partial_retrieval_absent_text_in_prompt() -> None:
    """Mixed retrieval: HbA1c found, TSH absent → LLM called, absent_text non-empty.

    Verifies the _build_inputs absent_text branch is exercised when at least one
    biomarker is recognized but has no records while another does have records.
    """
    repo = MagicMock(spec=BiomarkerRepository)

    # Return HbA1c record for hba1c; return empty for tsh
    def _side_effect_repo(patient_id: object, canonical_id: str) -> list[BiomarkerRecordRow]:
        if canonical_id == "hba1c":
            return [_make_record()]
        return []

    repo.find_by_canonical_id.side_effect = _side_effect_repo

    from src.gateway.gateway import Gateway

    gw = Gateway(prompts_dir=_PROMPTS_DIR)
    handler = NlqHandler(gateway=gw, biomarker_repo=repo)

    captured_inputs: dict[str, str] = {}

    def _capture_call(*args: Any, **kwargs: Any) -> tuple[dict[str, Any], int, int]:
        # Capture the user_content to verify absent_text was included
        nonlocal captured_inputs
        user_content = kwargs.get("user_content", args[2] if len(args) > 2 else "")
        captured_inputs["user_content"] = str(user_content)
        return (_GOOD_RAW, 50, 20)

    with patch(
        "src.gateway.anthropic_adapter.AnthropicAdapter.call",
        side_effect=_capture_call,
    ):
        resp = handler.answer("show me my HbA1c and TSH", _PATIENT_ID)

    assert resp.is_fallback is False
    assert resp.retrieval_count >= 1
    assert "No data found for" in captured_inputs.get("user_content", "")


# ── AC6: audit log ────────────────────────────────────────────────────────────


def test_answer_logs_audit_event() -> None:
    """AC6: audit_repo.record is called with event_type='nlq_answered'."""
    audit_repo = MagicMock()
    handler = _make_handler(audit_repo=audit_repo)

    with patch(
        "src.gateway.anthropic_adapter.AnthropicAdapter.call",
        return_value=(_GOOD_RAW, 50, 20),
    ):
        handler.answer("what's my HbA1c?", _PATIENT_ID)

    audit_repo.record.assert_called_once()
    call_kwargs = audit_repo.record.call_args
    assert call_kwargs.kwargs["event_type"] == "nlq_answered"
