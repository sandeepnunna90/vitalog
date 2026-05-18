"""Observation Generator (F2) — produces factual 1-3 sentence observations per biomarker record."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from src.gateway.citation_verifier_mode_b import verify as verify_mode_b
from src.gateway.errors import ModeBVerificationError, OutputValidationError
from src.gateway.gateway import Gateway
from src.intelligence.observation_schemas import Observation, ObservationCitation, ObservationOutput
from src.intelligence.trend_engine import TrendEngine
from src.intelligence.trend_schemas import TrendBand, TrendResult
from src.persistence.biomarker_repository import BiomarkerRepository
from src.persistence.models import BiomarkerRecordRow

_SAFE_REFUSAL = (
    "This observation could not be generated for this record. Please review the raw value directly."
)
_PROMPT_ID = "observation"
_PROMPT_VERSION = "v1"

_audit_log = logging.getLogger("audit")


class ObservationGenerator:
    def __init__(
        self,
        gateway: Gateway,
        biomarker_repo: BiomarkerRepository,
        trend_engine: TrendEngine,
        audit_repo: Any | None = None,
    ) -> None:
        self._gateway = gateway
        self._repo = biomarker_repo
        self._trend_engine = trend_engine
        self._audit = audit_repo

    def generate(
        self,
        record_id: uuid.UUID,
        patient_conditions: list[str] | None = None,
    ) -> Observation:
        """Generate a factual 1-3 sentence observation for a single biomarker record.

        AC6: if Mode B verification fails on both attempts, returns a safe-refusal
        observation rather than raising — the caller always receives a complete Observation.
        """
        record = self._repo.get(record_id)
        if record is None:
            raise ValueError(f"BiomarkerRecord {record_id} not found")
        if record.canonical_biomarker_id is None:
            raise ValueError(
                f"BiomarkerRecord {record_id} has no canonical_biomarker_id "
                "(pending-taxonomy records cannot be observed)"
            )

        trend = self._trend_engine.get_trend(
            record.patient_id,
            record.canonical_biomarker_id,
            patient_conditions,
        )
        retrieval_set = _build_retrieval_set(record, trend.bands)
        inputs = _build_inputs(record, trend)

        output = self._attempt(inputs, retrieval_set)
        text = output.text if output is not None else _SAFE_REFUSAL
        citations: list[ObservationCitation] = output.citations if output is not None else []

        self._log_audit(record_id)
        return Observation(
            record_id=record_id,
            text=text,
            citations=citations,
            prompt_version=_PROMPT_VERSION,
        )

    def _attempt(
        self,
        inputs: dict[str, str],
        retrieval_set: dict[uuid.UUID, BiomarkerRecordRow],
    ) -> ObservationOutput | None:
        try:
            out = self._gateway.call(_PROMPT_ID, _PROMPT_VERSION, inputs, ObservationOutput)
            verify_mode_b(out.text, retrieval_set)
            return out
        except (ModeBVerificationError, OutputValidationError) as exc:
            _audit_log.warning("observation attempt failed: %s: %s", type(exc).__name__, exc)
            return None

    def _log_audit(self, record_id: uuid.UUID) -> None:
        _audit_log.info(
            "observation_generated",
            extra={"record_id": str(record_id), "prompt_version": _PROMPT_VERSION},
        )
        if self._audit is not None:
            try:
                self._audit.record(
                    actor="system",
                    event_type="observation_generated",
                    payload={
                        "record_id": str(record_id),
                        "prompt_id": _PROMPT_ID,
                        "prompt_version": _PROMPT_VERSION,
                    },
                )
            except Exception as _exc:  # noqa: BLE001
                _audit_log.warning("audit_log_failed: %s", _exc)


# ── Module-level helpers ──────────────────────────────────────────────────────


def _build_retrieval_set(
    record: BiomarkerRecordRow,
    bands: list[TrendBand],
) -> dict[uuid.UUID, BiomarkerRecordRow]:
    """Build the Mode B retrieval set: the record + synthetic records for guideline bounds."""
    rs: dict[uuid.UUID, BiomarkerRecordRow] = {record.record_id: record}
    for band in bands:
        for bound in (band.lower, band.upper):
            if bound is not None:
                synth = _make_guideline_record(bound, record.canonical_unit, record.patient_id)
                rs[synth.record_id] = synth
    return rs


def _make_guideline_record(
    value: float,
    unit: str | None,
    patient_id: uuid.UUID,
) -> BiomarkerRecordRow:
    """Synthetic BiomarkerRecordRow for a guideline bound value (Mode B retrieval set only)."""
    return BiomarkerRecordRow(
        record_id=uuid.uuid4(),
        patient_id=patient_id,
        document_id=None,
        canonical_biomarker_id=None,
        pending_taxonomy_id=None,
        original_name="_guideline_bound",
        original_value=str(value),
        original_unit=unit,
        original_range=None,
        canonical_value=value,
        canonical_unit=unit,
        collection_date=None,
        lab_source=None,
        extraction_confidence=None,
        verified_by="auto",
        created_at=datetime.now(tz=UTC),
    )


def _build_inputs(record: BiomarkerRecordRow, trend: TrendResult) -> dict[str, str]:
    """Format prompt inputs from a record and its trend result."""
    value_str = (
        str(record.canonical_value) if record.canonical_value is not None else record.original_value
    )
    unit_str = record.canonical_unit or record.original_unit or ""

    if record.collection_date is not None:
        d = record.collection_date
        # Month-first so Mode B's false-positive filter skips the day number
        collection_date_str = f"{d.strftime('%B')} {d.day}, {d.year}"
    else:
        collection_date_str = "unknown date"

    guideline_lines: list[str] = []
    for band in trend.bands:
        line = f"- {band.label}: {band.raw_range}"
        if band.citation:
            line += f" (Source: {band.citation})"
        guideline_lines.append(line)

    guideline_text = (
        "\n".join(guideline_lines) if guideline_lines else "No published ranges available."
    )

    return {
        "biomarker_name": record.original_name,
        "value": value_str,
        "unit": unit_str,
        "collection_date": collection_date_str,
        "guideline_text": guideline_text,
        "record_id": str(record.record_id),
    }
