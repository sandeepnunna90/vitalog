"""Summary Generator (F5) — one-page health summary with Mode A citation verification."""

from __future__ import annotations

import logging
import uuid
from datetime import date
from typing import Any

from src.gateway.citation_schemas import Citation
from src.gateway.citation_verifier_mode_a import verify as verify_mode_a
from src.gateway.errors import BannedPhraseViolation, ModeAVerificationError, OutputValidationError
from src.gateway.gateway import Gateway
from src.intelligence.summary_schemas import Summary, SummaryOutput, SummaryOutputCitation
from src.persistence.biomarker_repository import BiomarkerRepository
from src.persistence.models import BiomarkerRecordRow
from src.persistence.patient_repository import PatientRepository

# Scope: AI generation provenance (this output came from an LLM, not a clinician).
# Deliberately different from context_cards.DISCLAIMER which covers reference-data accuracy.
DISCLAIMER = (
    "This summary was prepared by Vitalog from patient-uploaded records. "
    "It is not a medical document and does not constitute medical advice. "
    "Please verify all information with your healthcare provider."
)

_PROMPT_ID = "summary"
_PROMPT_VERSION = "v4"
_ACCEPTED_VERIFIED_BY = frozenset({"auto", "user", "admin"})

_audit_log = logging.getLogger("audit")


class SummaryGenerator:
    def __init__(
        self,
        gateway: Gateway,
        biomarker_repo: BiomarkerRepository,
        patient_repo: PatientRepository,
        audit_repo: Any | None = None,
    ) -> None:
        self._gateway = gateway
        self._repo = biomarker_repo
        self._patient_repo = patient_repo
        self._audit = audit_repo

    def generate(self, patient_id: uuid.UUID) -> Summary:
        """Produce a one-page health summary for the patient from all stored records.

        All numeric values are citation-verified (Mode A). Mode A verification is
        retried once on failure. If both attempts fail, returns a safe-refusal Summary
        with is_fallback=True and empty sections.
        Disclaimer is always appended by code — never LLM-generated.
        """
        patient = self._patient_repo.get(patient_id)
        all_records = self._repo.list_for_patient(patient_id)

        accepted = [
            r
            for r in all_records
            if r.canonical_value is not None
            and r.collection_date is not None
            and r.verified_by in _ACCEPTED_VERIFIED_BY
        ]

        if not accepted:
            return Summary(
                patient_id=patient_id,
                conditions_section="",
                results_section="No accepted biomarker records found.",
                trends_section="",
                data_gaps_section="",
                patient_notes="",
                citations=[],
                disclaimer=DISCLAIMER,
                prompt_version=_PROMPT_VERSION,
                citation_count=0,
                is_fallback=True,
            )

        retrieval_set: dict[uuid.UUID, BiomarkerRecordRow] = {r.record_id: r for r in accepted}
        inputs = _build_inputs(patient, accepted)

        result = self._attempt(inputs, retrieval_set, patient_id)
        if result is None:
            result = self._attempt(inputs, retrieval_set, patient_id)
        is_fallback = result is None
        out, citations = result if result is not None else (None, [])
        citation_count = len(citations)

        summary = Summary(
            patient_id=patient_id,
            conditions_section=out.conditions_section if out else "",
            results_section=out.results_section if out else "",
            trends_section=out.trends_section if out else "",
            data_gaps_section=out.data_gaps_section if out else "",
            patient_notes=out.patient_notes if out else "",
            citations=citations,
            disclaimer=DISCLAIMER,
            prompt_version=_PROMPT_VERSION,
            citation_count=citation_count,
            is_fallback=is_fallback,
        )

        self._log_audit(patient_id, citation_count)
        return summary

    def _attempt(
        self,
        inputs: dict[str, str],
        retrieval_set: dict[uuid.UUID, BiomarkerRecordRow],
        patient_id: uuid.UUID,
    ) -> tuple[SummaryOutput, list[Citation]] | None:
        try:
            out = self._gateway.call(_PROMPT_ID, _PROMPT_VERSION, inputs, SummaryOutput)
            citations = _convert_citations(out.citations)
            verify_mode_a(citations, patient_id, retrieval_set)
            return out, citations
        except (  # noqa: E501 — four exception types is intentional; see src/gateway/errors.py
            BannedPhraseViolation,
            ModeAVerificationError,
            OutputValidationError,
            ValueError,
        ) as exc:
            _audit_log.warning("summary attempt failed: %s: %s", type(exc).__name__, exc)
            return None

    def _log_audit(self, patient_id: uuid.UUID, citation_count: int) -> None:
        _audit_log.info(
            "summary_generated",
            extra={
                "patient_id": str(patient_id),
                "citation_count": citation_count,
                "prompt_version": _PROMPT_VERSION,
            },
        )
        if self._audit is not None:
            try:
                self._audit.record(
                    actor="system",
                    event_type="summary_generated",
                    payload={
                        "patient_id": str(patient_id),
                        "citation_count": citation_count,
                        "prompt_id": _PROMPT_ID,
                        "prompt_version": _PROMPT_VERSION,
                    },
                )
            except Exception as _exc:  # noqa: BLE001
                _audit_log.warning("audit_log_failed: %s", _exc)


# ── Module-level helpers ──────────────────────────────────────────────────────


def _convert_citations(raw: list[SummaryOutputCitation]) -> list[Citation]:
    """Convert LLM string-typed citations to properly typed Citation objects.

    Raises ValueError if any collection_date is not ISO format or source_record_id
    is not a valid UUID — triggers retry in _attempt().
    """
    return [
        Citation(
            value=c.value,
            unit=c.unit,
            collection_date=date.fromisoformat(c.collection_date),
            source_record_id=uuid.UUID(c.source_record_id),
        )
        for c in raw
    ]


def _build_inputs(
    patient: Any,
    accepted_records: list[BiomarkerRecordRow],
) -> dict[str, str]:
    """Format LLM prompt inputs from patient info and records."""
    if patient is not None:
        dob_str = patient.dob.strftime("%B %d, %Y") if patient.dob else "Unknown"
        profile_text = f"Name: {patient.name}, Date of Birth: {dob_str}"
    else:
        profile_text = "Name: Unknown"

    for r in accepted_records:
        assert r.collection_date is not None, f"record {r.record_id} slipped past accepted filter"
    sorted_records = sorted(
        accepted_records,
        key=lambda r: (r.original_name, r.collection_date),
    )
    record_lines: list[str] = []
    for r in sorted_records:
        value_str = str(r.canonical_value)
        unit_str = r.canonical_unit or r.original_unit or ""
        d = r.collection_date
        assert d is not None
        date_str = f"{d.strftime('%B')} {d.day}, {d.year}"
        value_unit = f"{value_str} {unit_str}".rstrip()
        record_lines.append(f"{r.original_name}: {value_unit} — {date_str} [id={r.record_id}]")

    return {
        "profile_text": profile_text,
        "records_text": "\n".join(record_lines) if record_lines else "No records available.",
        # Hardcoded to "None" — conditions are no longer in the patient profile after
        # moving to DB-loaded patient (name/dob only). Gap detection is deferred until
        # conditions are stored in the patient table.
        "data_gaps_text": "None",
    }
