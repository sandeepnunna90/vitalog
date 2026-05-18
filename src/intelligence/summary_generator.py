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
from src.intelligence.retrieval import canonical_name
from src.intelligence.summary_schemas import Summary, SummaryOutput, SummaryOutputCitation
from src.persistence.biomarker_repository import BiomarkerRepository
from src.persistence.models import BiomarkerRecordRow
from src.reference_data import load_biomarker_groups, load_patient_profile

DISCLAIMER = (
    "This summary was prepared by Vitalog from patient-uploaded records. "
    "It is not a medical document and does not constitute medical advice. "
    "Please verify all information with your healthcare provider."
)

_PROMPT_ID = "summary"
_PROMPT_VERSION = "v2"
_ACCEPTED_VERIFIED_BY = frozenset({"auto", "user", "admin"})

_audit_log = logging.getLogger("audit")


class SummaryGenerator:
    def __init__(
        self,
        gateway: Gateway,
        biomarker_repo: BiomarkerRepository,
        audit_repo: Any | None = None,
    ) -> None:
        self._gateway = gateway
        self._repo = biomarker_repo
        self._audit = audit_repo

    def generate(self, patient_id: uuid.UUID) -> Summary:
        """Produce a one-page health summary for the patient from all stored records.

        All numeric values are citation-verified (Mode A). If both attempts fail,
        returns a safe-refusal Summary with is_fallback=True and empty sections.
        Disclaimer is always appended by code — never LLM-generated.
        """
        profile = load_patient_profile()
        all_records = self._repo.list_for_patient(patient_id)

        accepted = [
            r
            for r in all_records
            if r.canonical_value is not None
            and r.collection_date is not None
            and r.verified_by in _ACCEPTED_VERIFIED_BY
        ]

        retrieval_set: dict[uuid.UUID, BiomarkerRecordRow] = {r.record_id: r for r in accepted}
        gaps = _detect_data_gaps(profile.conditions, accepted)
        inputs = _build_inputs(profile, accepted, gaps)

        result = self._attempt(inputs, retrieval_set, patient_id)
        is_fallback = result is None
        out, citations = result if result is not None else (None, [])
        citation_count = len(citations)

        summary = Summary(
            patient_id=patient_id,
            conditions_section=out.conditions_section if out else "",
            medications_section=out.medications_section if out else "",
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
        except (
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
            except Exception:  # noqa: BLE001
                pass  # audit failure must never break the caller


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


def _detect_data_gaps(
    conditions: list[str],
    accepted_records: list[BiomarkerRecordRow],
) -> list[str]:
    """Return canonical names of condition-relevant biomarkers with no accepted records."""
    recorded_ids: set[str] = {
        r.canonical_biomarker_id for r in accepted_records if r.canonical_biomarker_id is not None
    }
    groups = load_biomarker_groups()["conditions"]
    seen: set[str] = set()
    gaps: list[str] = []
    for cond in conditions:
        if cond not in groups:
            _audit_log.warning("unknown condition code in profile, skipping: %s", cond)
            continue
        for cid in groups[cond].get("biomarkers", []):
            if cid not in recorded_ids and cid not in seen:
                seen.add(cid)
                gaps.append(canonical_name(cid))
    return gaps


def _build_inputs(
    profile: Any,
    accepted_records: list[BiomarkerRecordRow],
    gaps: list[str],
) -> dict[str, str]:
    """Format LLM prompt inputs from the patient profile, records, and data gaps."""
    groups = load_biomarker_groups()["conditions"]

    condition_lines: list[str] = []
    for cond in profile.conditions:
        display = groups[cond]["display_name"] if cond in groups else cond
        condition_lines.append(display)

    allergy_lines = [f"{a.substance} ({a.severity})" for a in profile.allergies]
    med_lines = [f"{m.name} {m.dose}" for m in profile.medications]

    profile_text = (
        f"Conditions: {', '.join(condition_lines) if condition_lines else 'None'}\n"
        f"Medications: {', '.join(med_lines) if med_lines else 'None'}\n"
        f"Allergies: {', '.join(allergy_lines) if allergy_lines else 'None'}"
    )

    sorted_records = sorted(
        accepted_records,
        key=lambda r: (r.original_name, r.collection_date),
    )
    record_lines: list[str] = []
    for r in sorted_records:
        value_str = str(r.canonical_value)
        unit_str = r.canonical_unit or r.original_unit or ""
        d = r.collection_date
        assert d is not None  # accepted filter guarantees non-None collection_date
        date_str = f"{d.strftime('%B')} {d.day}, {d.year}"
        value_unit = f"{value_str} {unit_str}".rstrip()
        record_lines.append(f"{r.original_name}: {value_unit} — {date_str} [id={r.record_id}]")

    data_gaps_text = "\n".join(gaps) if gaps else "None"

    return {
        "profile_text": profile_text,
        "records_text": "\n".join(record_lines) if record_lines else "No records available.",
        "data_gaps_text": data_gaps_text,
    }
