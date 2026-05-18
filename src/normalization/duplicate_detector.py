"""E4 — Duplicate detection for normalized biomarker records."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict

from src.normalization.constants import MODE_B_NUMERIC_TOLERANCE, within_tolerance
from src.persistence.audit_log_repository import AuditLogRepository
from src.persistence.biomarker_repository import BiomarkerRepository
from src.persistence.models import BiomarkerRecordRow


class DuplicateCheckResult(BaseModel):
    model_config = ConfigDict(strict=True)

    status: Literal["duplicate", "value_conflict", "no_match", "skipped_no_date"]
    prior_record_id: uuid.UUID | None = None
    prior_lab_source: str | None = None
    prior_collection_date: date | None = None
    # Populated only when status == "duplicate"
    notification_message: str | None = None


class DuplicateDetector:
    def __init__(
        self,
        biomarker_repo: BiomarkerRepository,
        audit_repo: AuditLogRepository,
    ) -> None:
        self._biomarker_repo = biomarker_repo
        self._audit_repo = audit_repo

    def check(
        self,
        patient_id: uuid.UUID,
        canonical_id: str,
        collection_date: date | None,
        canonical_value: float,
        new_record_id: uuid.UUID,
    ) -> DuplicateCheckResult:
        """Detect whether a newly stored record duplicates an existing one.

        Called AFTER the new record is persisted so both record_ids are available
        for the audit event. new_record_id is excluded from comparison to avoid
        self-match when the new record is already in the query results.

        Records whose canonical_value is None are skipped — no value to compare.
        An exact duplicate (within tolerance) takes priority over a value_conflict:
        the loop continues past any conflict priors to check all remaining records.
        """
        if collection_date is None:
            self._audit_repo.record(
                actor="normalization",
                event_type="dedup_skipped_no_date",
                payload={"new_record_id": str(new_record_id), "canonical_id": canonical_id},
            )
            return DuplicateCheckResult(status="skipped_no_date")

        prior_records = self._biomarker_repo.find_potential_duplicates(
            patient_id, canonical_id, collection_date
        )

        # Accumulate the first conflict found; keep iterating in case a later
        # prior is an exact duplicate (duplicate takes priority over conflict).
        conflict_prior: BiomarkerRecordRow | None = None

        for prior in prior_records:
            if prior.record_id == new_record_id:
                continue
            if prior.canonical_value is None:
                continue

            ref = prior.canonical_value
            if within_tolerance(canonical_value, ref, MODE_B_NUMERIC_TOLERANCE):
                self._audit_repo.record(
                    actor="normalization",
                    event_type="duplicate_detected",
                    payload={
                        "prior_record_id": str(prior.record_id),
                        "new_record_id": str(new_record_id),
                    },
                )
                return DuplicateCheckResult(
                    status="duplicate",
                    prior_record_id=prior.record_id,
                    prior_lab_source=prior.lab_source,
                    prior_collection_date=prior.collection_date,
                    notification_message=_build_notification(collection_date, prior.lab_source),
                )
            elif conflict_prior is None:
                conflict_prior = prior

        if conflict_prior is not None:
            self._audit_repo.record(
                actor="normalization",
                event_type="value_conflict",
                payload={
                    "prior_record_id": str(conflict_prior.record_id),
                    "new_record_id": str(new_record_id),
                    "value_conflict": True,
                },
            )
            return DuplicateCheckResult(
                status="value_conflict",
                prior_record_id=conflict_prior.record_id,
                prior_lab_source=conflict_prior.lab_source,
                prior_collection_date=conflict_prior.collection_date,
            )

        return DuplicateCheckResult(status="no_match")


def _build_notification(collection_date: date, lab_source: str | None) -> str:
    # %-d strips leading zero ("March 5" not "March 05"); Python 3.12+ normalises cross-platform
    date_str = collection_date.strftime("%B %-d")
    if lab_source:
        return f"This looks like a duplicate of your {date_str} {lab_source} report."
    return f"This looks like a duplicate of your {date_str} report."
