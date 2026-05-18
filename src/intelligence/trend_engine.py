"""Trend Engine — pure deterministic biomarker trend computation (no LLM)."""

from __future__ import annotations

import uuid

from src.intelligence.range_overlay import select_bands
from src.intelligence.trend_schemas import TrendPoint, TrendResult
from src.persistence.biomarker_repository import BiomarkerRepository
from src.persistence.models import BiomarkerRecordRow
from src.reference_data import lookup_guideline

_ACCEPTED_VERIFIED_BY = frozenset({"auto", "user", "admin"})


def _to_point(row: BiomarkerRecordRow) -> TrendPoint:
    assert row.collection_date is not None, f"record {row.record_id} has no collection_date"
    assert row.canonical_value is not None, f"record {row.record_id} has no canonical_value"
    return TrendPoint(
        record_id=row.record_id,
        collection_date=row.collection_date,
        canonical_value=row.canonical_value,
        canonical_unit=row.canonical_unit or "",
        lab_source=row.lab_source,
        verified_by=row.verified_by,
        extraction_confidence=row.extraction_confidence,
    )


class TrendEngine:
    def __init__(self, biomarker_repo: BiomarkerRepository) -> None:
        self._repo = biomarker_repo

    def get_trend(
        self,
        patient_id: uuid.UUID,
        canonical_id: str,
        patient_conditions: list[str] | None = None,
    ) -> TrendResult:
        all_records = self._repo.find_by_canonical_id(patient_id, canonical_id)
        pending_count = sum(1 for r in all_records if r.verified_by == "pending_user")

        trend_records = [
            r
            for r in all_records
            if r.verified_by in _ACCEPTED_VERIFIED_BY
            and r.canonical_value is not None
            and r.collection_date is not None
        ]
        points = sorted(
            [_to_point(r) for r in trend_records],
            key=lambda p: p.collection_date,
        )

        guideline = lookup_guideline(canonical_id)
        bands = (
            select_bands(
                guideline["guideline_ranges"],
                guideline["guideline_citations"],
                patient_conditions or [],
            )
            if guideline
            else []
        )

        return TrendResult(
            patient_id=patient_id,
            canonical_id=canonical_id,
            canonical_unit=points[0].canonical_unit if points else None,
            points=points,
            bands=bands,
            pending_review_count=pending_count,
        )
