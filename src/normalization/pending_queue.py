"""Tier 4 — enqueue unrecognized biomarker names into the pending taxonomy queue."""

from __future__ import annotations

import uuid

from src.persistence.models import PendingTaxonomyEntryCreate, PendingTaxonomyEntryRow
from src.persistence.taxonomy_repository import TaxonomyRepository


class PendingQueue:
    def __init__(self, taxonomy_repo: TaxonomyRepository) -> None:
        self._repo = taxonomy_repo

    def enqueue(
        self,
        raw_name: str,
        document_id: uuid.UUID | None = None,
        raw_unit: str | None = None,
    ) -> PendingTaxonomyEntryRow:
        """Stage an unrecognized biomarker name for admin review.

        candidate_loinc_codes and similarity_to_existing are empty for capstone;
        Tier 2 / Tier 3 (deferred to v1) would populate them.
        """
        entry = PendingTaxonomyEntryCreate(
            raw_name=raw_name,
            document_id=document_id,
            raw_unit=raw_unit,
        )
        return self._repo.add_pending(entry)
