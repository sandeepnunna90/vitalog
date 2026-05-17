"""E4 — Duplicate detection for normalized biomarker records."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict

from src.normalization.constants import MODE_B_NUMERIC_TOLERANCE
from src.persistence.audit_log_repository import AuditLogRepository
from src.persistence.biomarker_repository import BiomarkerRepository


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
        """
        if collection_date is None:
            return DuplicateCheckResult(status="skipped_no_date")

        prior_records = self._biomarker_repo.find_potential_duplicates(
            patient_id, canonical_id, collection_date
        )

        for prior in prior_records:
            if prior.record_id == new_record_id:
                continue
            if prior.canonical_value is None:
                continue

            ref = prior.canonical_value
            if ref == 0.0:
                within_tolerance = canonical_value == 0.0
            else:
                within_tolerance = abs(canonical_value - ref) / abs(ref) <= MODE_B_NUMERIC_TOLERANCE

            if within_tolerance:
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
            else:
                self._audit_repo.record(
                    actor="normalization",
                    event_type="value_conflict",
                    payload={
                        "prior_record_id": str(prior.record_id),
                        "new_record_id": str(new_record_id),
                        "value_conflict": True,
                    },
                )
                return DuplicateCheckResult(
                    status="value_conflict",
                    prior_record_id=prior.record_id,
                    prior_lab_source=prior.lab_source,
                    prior_collection_date=prior.collection_date,
                )

        return DuplicateCheckResult(status="no_match")


def _build_notification(collection_date: date, lab_source: str | None) -> str:
    date_str = collection_date.strftime("%B %-d")
    if lab_source:
        return f"This looks like a duplicate of your {date_str} {lab_source} report."
    return f"This looks like a duplicate of your {date_str} report."
