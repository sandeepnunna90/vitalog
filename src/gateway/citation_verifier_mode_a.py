"""Mode A citation verifier — deterministic, zero LLM calls."""

from __future__ import annotations

import logging
import uuid

from src.gateway.citation_schemas import Citation
from src.gateway.errors import ModeAVerificationError, OwnershipLeakError
from src.persistence.models import BiomarkerRecordRow

MODE_A_NUMERIC_TOLERANCE = 0.005  # ±0.5 % per §7.2.1

_security_log = logging.getLogger("verification.security")


def verify(
    citations: list[Citation],
    patient_id: uuid.UUID,
    retrieval_set: dict[uuid.UUID, BiomarkerRecordRow],
) -> None:
    """Verify all Mode A citations against the retrieval set.

    Raises ModeAVerificationError (or OwnershipLeakError) on any failure.
    Returns None on success. Zero I/O — pure deterministic.
    """
    for citation in citations:
        record = retrieval_set.get(citation.source_record_id)

        # Retrieval-set check (AC2) — citation outside permitted scope is a security event
        if record is None:
            _security_log.error(
                "Mode A: citation not in retrieval set",
                extra={
                    "source_record_id": str(citation.source_record_id),
                    "patient_id": str(patient_id),
                },
            )
            raise ModeAVerificationError(
                reason="source_record_id not in retrieval set",
                citation=citation,
            )

        # Ownership check (AC4) — patient_id mismatch is a security event
        if record.patient_id != patient_id:
            _security_log.error(
                "Mode A: ownership leak",
                extra={
                    "source_record_id": str(citation.source_record_id),
                    "record_patient_id": str(record.patient_id),
                    "generation_patient_id": str(patient_id),
                },
            )
            raise OwnershipLeakError(
                reason="patient_id mismatch — ownership leak",
                citation=citation,
            )

        # Unit exact match (AC1)
        if record.canonical_unit != citation.unit:
            raise ModeAVerificationError(
                reason=f"unit mismatch: stored={record.canonical_unit!r}, cited={citation.unit!r}",
                citation=citation,
            )

        # Date exact match (AC1)
        if record.collection_date != citation.collection_date:
            raise ModeAVerificationError(
                reason="collection_date mismatch",
                citation=citation,
            )

        # Numeric tolerance ±0.5% (AC1, AC3)
        if record.canonical_value is None:
            raise ModeAVerificationError(
                reason="stored record has no canonical_value",
                citation=citation,
            )
        stored = record.canonical_value
        if stored == 0.0:
            if citation.value != 0.0:
                raise ModeAVerificationError(
                    reason=f"value mismatch: stored=0.0, cited={citation.value}",
                    citation=citation,
                )
        else:
            pct_diff = abs(citation.value - stored) / abs(stored)
            if pct_diff > MODE_A_NUMERIC_TOLERANCE:
                raise ModeAVerificationError(
                    reason=(
                        f"value {citation.value} differs from stored {stored} "
                        f"by {pct_diff:.3%} (limit {MODE_A_NUMERIC_TOLERANCE:.1%})"
                    ),
                    citation=citation,
                )
