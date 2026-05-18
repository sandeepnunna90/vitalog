"""NLQ Handler (F3) — retrieval-first natural language query over stored biomarker records."""

from __future__ import annotations

import logging
import uuid
from datetime import date
from typing import Any

from src.gateway.citation_verifier_mode_b import verify as verify_mode_b
from src.gateway.errors import ModeBVerificationError, OutputValidationError
from src.gateway.gateway import Gateway
from src.intelligence.nlq_schemas import NlqOutput, NlqResponse
from src.intelligence.retrieval import canonical_name, resolve_query
from src.persistence.biomarker_repository import BiomarkerRepository
from src.persistence.models import BiomarkerRecordRow

_SAFE_REFUSAL = "I can only answer questions about your stored health records."
_PROMPT_ID = "nlq"
_PROMPT_VERSION = "v1"

_audit_log = logging.getLogger("audit")


class NlqHandler:
    def __init__(
        self,
        gateway: Gateway,
        biomarker_repo: BiomarkerRepository,
        audit_repo: Any | None = None,
    ) -> None:
        self._gateway = gateway
        self._repo = biomarker_repo
        self._audit = audit_repo

    def answer(
        self,
        query: str,
        patient_id: uuid.UUID,
    ) -> NlqResponse:
        """Answer a natural-language query using only the patient's stored records.

        AC5: retrieval always runs before the LLM is called — no path skips this step.
        AC3/AC6: if Mode B verification fails on both attempts, returns safe-refusal text.
        """
        result = resolve_query(query, patient_id, self._repo)

        if not result.retrieval_set and not result.missing_canonical_ids:
            self._log_audit(query, 0)
            return NlqResponse(
                text=_SAFE_REFUSAL,
                retrieval_count=0,
                prompt_version=_PROMPT_VERSION,
                is_fallback=True,
                matched_condition_names=[],
            )

        if not result.retrieval_set:
            text = _missing_fallback(result.missing_canonical_ids)
            if result.matched_condition_names:
                text = text + _condition_group_disclaimer(result.matched_condition_names)
            self._log_audit(query, 0)
            return NlqResponse(
                text=text,
                retrieval_count=0,
                prompt_version=_PROMPT_VERSION,
                is_fallback=True,
                matched_condition_names=result.matched_condition_names,
            )

        inputs = _build_inputs(query, result.retrieval_set, result.missing_canonical_ids)

        output = self._attempt(inputs, result.retrieval_set)
        if output is None:
            output = self._attempt(inputs, result.retrieval_set)

        text = output.text if output is not None else _SAFE_REFUSAL
        if result.matched_condition_names and output is not None:
            text = text + _condition_group_disclaimer(result.matched_condition_names)
        self._log_audit(query, len(result.retrieval_set))
        return NlqResponse(
            text=text,
            retrieval_count=len(result.retrieval_set),
            prompt_version=_PROMPT_VERSION,
            is_fallback=output is None,
            matched_condition_names=result.matched_condition_names,
        )

    def _attempt(
        self,
        inputs: dict[str, str],
        retrieval_set: dict[uuid.UUID, BiomarkerRecordRow],
    ) -> NlqOutput | None:
        try:
            out = self._gateway.call(_PROMPT_ID, _PROMPT_VERSION, inputs, NlqOutput)
            verify_mode_b(out.text, retrieval_set)
            return out
        except (ModeBVerificationError, OutputValidationError) as exc:
            _audit_log.warning("nlq attempt failed: %s: %s", type(exc).__name__, exc)
            return None

    def _log_audit(self, query: str, retrieval_count: int) -> None:
        _audit_log.info(
            "nlq_answered",
            extra={
                "query_length": len(query),
                "retrieval_count": retrieval_count,
                "prompt_version": _PROMPT_VERSION,
            },
        )
        if self._audit is not None:
            try:
                self._audit.record(
                    actor="system",
                    event_type="nlq_answered",
                    payload={
                        "query_length": len(query),
                        "retrieval_count": retrieval_count,
                        "prompt_id": _PROMPT_ID,
                        "prompt_version": _PROMPT_VERSION,
                    },
                )
            except Exception:  # noqa: BLE001
                pass  # audit failure must never break the caller


# ── Module-level helpers ──────────────────────────────────────────────────────


def _missing_fallback(missing_ids: list[str]) -> str:
    names = [canonical_name(cid) for cid in missing_ids]
    if len(names) == 1:
        return (
            f"We don't have any {names[0]} results yet. "
            "Upload a lab report that includes this test."
        )
    joined = ", ".join(names)
    return f"We don't have results for {joined} yet. Upload a lab report that includes these tests."


def _condition_group_disclaimer(names: list[str]) -> str:
    joined = ", ".join(names)
    return (
        f"\n\nThese biomarkers are commonly grouped with {joined} based on clinical guidelines"
        " — speak with your provider about what's relevant for you."
    )


def _build_inputs(
    query: str,
    retrieval_set: dict[uuid.UUID, BiomarkerRecordRow],
    missing_ids: list[str],
) -> dict[str, str]:
    """Format prompt inputs from query, retrieval set, and missing biomarker IDs."""
    records = sorted(
        retrieval_set.values(),
        key=lambda r: (r.collection_date or date.min, r.original_name),
    )
    record_lines: list[str] = []
    for r in records:
        value_str = str(r.canonical_value) if r.canonical_value is not None else r.original_value
        unit_str = r.canonical_unit or r.original_unit or ""
        if r.collection_date is not None:
            d = r.collection_date
            date_str = f"{d.strftime('%B')} {d.day}, {d.year}"
        else:
            date_str = "unknown date"
        value_unit = f"{value_str} {unit_str}".rstrip()
        record_lines.append(f"{r.original_name}: {value_unit} on {date_str}")

    absent_text = ""
    if missing_ids:
        names = [canonical_name(cid) for cid in missing_ids]
        absent_text = f"\nNote: No data found for: {', '.join(names)}."

    return {
        "query": query,
        "records_text": "\n".join(record_lines),
        "absent_text": absent_text,
    }
