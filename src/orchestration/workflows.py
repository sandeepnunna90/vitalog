"""Orchestration workflow coordinators — compose service calls for each MCP tool.

Each workflow is a pure function: takes a ServiceContainer (pre-built services)
and typed inputs, returns a typed result. No business logic lives here beyond
orchestrating the sequence of service calls.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict

from src.ingestion.date_extractor import extract_collection_date
from src.ingestion.errors import TextractFailureError
from src.ingestion.structurer_schemas import Band
from src.ingestion.textract_schemas import TextractResult
from src.ingestion.upload_validator import ValidatedUpload
from src.intelligence.exporter import export_summary as _export_summary
from src.intelligence.nlq_schemas import NlqResponse
from src.intelligence.trend_schemas import TrendResult
from src.normalization import tier1
from src.normalization.errors import UnitConversionError, UnitMissingError
from src.normalization.range_validator import validate_physiological_range
from src.normalization.unit_converter import convert
from src.orchestration.container import ServiceContainer
from src.persistence.models import BiomarkerRecordCreate, VerifiedBy

_log = logging.getLogger(__name__)


# ── Result schemas ────────────────────────────────────────────────────────────


class UploadResult(BaseModel):
    model_config = ConfigDict(strict=True)

    category: str
    document_id: uuid.UUID | None
    user_message: str
    auto_accepted: int
    pending_user: int
    rejected: int
    pending_taxonomy: int
    duplicate_skipped: int


class GenerateSummaryResult(BaseModel):
    model_config = ConfigDict(strict=True)

    summary_id: uuid.UUID
    is_fallback: bool
    conditions_section: str
    results_section: str
    trends_section: str
    data_gaps_section: str
    patient_notes: str
    disclaimer: str
    citation_count: int


# ── Workflows ─────────────────────────────────────────────────────────────────


def upload_document_workflow(
    file_bytes: bytes,
    filename: str,
    patient_id: uuid.UUID,
    container: ServiceContainer,
) -> UploadResult:
    """Full ingestion pipeline: validate → classify → store → OCR → structure → normalize → persist.

    Returns counts by band so the MCP tool can report a human-readable summary.
    """
    upload = container.validator.validate(file_bytes, filename)
    classification = container.classifier.classify(upload)
    route = container.storage_router.route(upload, classification, patient_id, filename)

    if not route.should_continue_pipeline:
        return UploadResult(
            category=classification.category.value,
            document_id=route.document_id,
            user_message=route.user_message,
            auto_accepted=0,
            pending_user=0,
            rejected=0,
            pending_taxonomy=0,
            duplicate_skipped=0,
        )

    doc_id = route.document_id
    assert doc_id is not None  # guaranteed when should_continue_pipeline=True

    try:
        textract_result = container.textract.extract(upload, doc_id)
    except TextractFailureError as exc:
        _log.warning("Textract unavailable (%s); routing to vision fallback.", exc)
        textract_result = TextractResult(blocks=[], tables=[], kv_pairs=[], page_count=1)
    textract_result = container.fallback.extract(upload, doc_id, textract_result)
    structurer_result = container.structurer.structure(
        textract_result, doc_id, classification.confidence
    )

    _full_text = _extract_full_text(upload, textract_result)
    document_date: date | None = extract_collection_date(_full_text)
    if document_date:
        _log.info("document-level collection date extracted: %s", document_date)
    else:
        _log.warning("no collection date found in document text — records will have NULL date")

    stats: dict[str, int] = {
        "auto_accepted": 0,
        "pending_user": 0,
        "rejected": 0,
        "pending_taxonomy": 0,
        "duplicate_skipped": 0,
    }

    for candidate in structurer_result.candidates:
        _normalize_and_persist(candidate, patient_id, doc_id, container, stats, document_date)

    return UploadResult(
        category=classification.category.value,
        document_id=doc_id,
        user_message=route.user_message,
        **stats,
    )


def list_biomarkers_workflow(
    patient_id: uuid.UUID,
    container: ServiceContainer,
    filter: str | None = None,
) -> list[dict[str, Any]]:
    """Return one entry per canonical biomarker the patient has data for.

    Each entry: canonical_biomarker_id, latest_value, latest_unit, latest_date,
    record_count. Sorted by canonical_biomarker_id. Optional filter narrows by
    canonical_biomarker_id prefix (case-insensitive).
    """
    rows = container.biomarker_repo.list_for_patient(patient_id)
    # Group by canonical_biomarker_id; fall back to original_name for pending-taxonomy records.
    groups: dict[str, list[Any]] = {}
    for row in rows:
        key = row.canonical_biomarker_id or f"__pending__{row.original_name}"
        groups.setdefault(key, []).append(row)

    results: list[dict[str, Any]] = []
    for key, group_rows in sorted(groups.items()):
        if filter and filter.lower() not in key.lower():
            continue
        # Latest record by collection_date (None dates sort last)
        latest = max(
            group_rows,
            key=lambda r: r.collection_date or date.min,
        )
        results.append(
            {
                "canonical_biomarker_id": latest.canonical_biomarker_id,
                "original_name": latest.original_name,
                "latest_value": latest.canonical_value,
                "latest_unit": latest.canonical_unit or latest.original_unit,
                "latest_date": latest.collection_date.isoformat()
                if latest.collection_date
                else None,
                "record_count": len(group_rows),
            }
        )
    return results


def view_trend_workflow(
    patient_id: uuid.UUID,
    biomarker_id: str,
    container: ServiceContainer,
) -> TrendResult:
    """Return longitudinal trend + guideline bands for a single biomarker."""
    return container.trend_engine.get_trend(patient_id, biomarker_id, patient_conditions=None)


def query_workflow(
    patient_id: uuid.UUID,
    question: str,
    container: ServiceContainer,
) -> NlqResponse:
    """Answer a natural-language question using the patient's stored records."""
    return container.nlq_handler.answer(question, patient_id)


def generate_summary_workflow(
    patient_id: uuid.UUID,
    container: ServiceContainer,
) -> GenerateSummaryResult:
    """Generate and persist an appointment summary; return the summary_id for export."""
    summary = container.summary_generator.generate(patient_id)
    row = container.annotator.persist(summary)
    return GenerateSummaryResult(
        summary_id=row.summary_id,
        is_fallback=summary.is_fallback,
        conditions_section=summary.conditions_section,
        results_section=summary.results_section,
        trends_section=summary.trends_section,
        data_gaps_section=summary.data_gaps_section,
        patient_notes=summary.patient_notes,
        disclaimer=summary.disclaimer,
        citation_count=summary.citation_count,
    )


def export_workflow(
    summary_id: uuid.UUID,
    format: str,
    patient_id: uuid.UUID,
    container: ServiceContainer,
) -> bytes:
    """Export a persisted summary as PDF, markdown, or JSON bytes.

    Raises ValueError if the summary does not belong to patient_id.
    """
    row = container.summary_repo.get(summary_id)
    if row is None or row.patient_id != patient_id:
        raise ValueError("summary not found")
    return _export_summary(
        summary_id=summary_id,
        format=format,
        summary_repo=container.summary_repo,
        audit_repo=container.audit_repo,
    )


# ── Private helpers ───────────────────────────────────────────────────────────


def _extract_full_text(upload: ValidatedUpload, textract_result: TextractResult) -> str:
    """Return all page text from the upload for date extraction.

    For PDFs, uses PyMuPDF to read the text layer across all pages (headers on
    every page typically repeat the collection date). Falls back to joining
    Textract block texts for images or when PyMuPDF fails. Never raises.
    """
    if upload.mime == "application/pdf":
        try:
            import fitz  # PyMuPDF — deferred import, consistent with project conventions

            fitz.TOOLS.mupdf_display_errors(False)  # suppress C-level stderr in all contexts
            with fitz.open(stream=upload.file_bytes, filetype="pdf") as doc:
                return "\n".join(page.get_text() for page in doc)
        except Exception as exc:  # noqa: BLE001
            _log.debug("_extract_full_text: PyMuPDF failed (%s), falling back to blocks", exc)
    return "\n".join(b.text for b in textract_result.blocks)


def _normalize_and_persist(
    candidate: Any,
    patient_id: uuid.UUID,
    doc_id: uuid.UUID,
    container: ServiceContainer,
    stats: dict[str, int],
    document_date: date | None = None,
) -> None:
    """Normalize one BiomarkerCandidate and write it to the repository.

    Mutates stats in-place. REJECT-band candidates are counted and skipped.
    """
    if candidate.band == Band.REJECT:
        stats["rejected"] += 1
        return

    new_id = uuid.uuid4()
    canonical_id = tier1.lookup(candidate.raw_name)

    collection_date: date | None = None
    if candidate.collection_date:
        # Attempt 1: ISO 8601 (YYYY-MM-DD) — fastest, correct when LLM behaves
        try:
            collection_date = date.fromisoformat(candidate.collection_date)
        except ValueError:
            pass
        # Attempt 2: dateutil — handles MM/DD/YYYY, "June 5 2019", etc.
        if collection_date is None:
            try:
                from dateutil import parser as _du

                collection_date = _du.parse(candidate.collection_date, dayfirst=False).date()
            except Exception:  # noqa: BLE001
                _log.warning("unparseable collection_date from LLM: %r", candidate.collection_date)
    # Attempt 3: document-level date extracted via regex from raw PDF text
    if collection_date is None and document_date is not None:
        collection_date = document_date

    if canonical_id is None:
        # Unrecognized biomarker — route to pending taxonomy queue
        pending_entry = container.pending_queue.enqueue(
            raw_name=candidate.raw_name,
            document_id=doc_id,
            raw_unit=candidate.raw_unit or None,
        )
        record = BiomarkerRecordCreate(
            patient_id=patient_id,
            document_id=doc_id,
            pending_taxonomy_id=pending_entry.pending_id,
            original_name=candidate.raw_name,
            original_value=candidate.raw_value,
            original_unit=candidate.raw_unit or None,
            original_range=candidate.raw_reference_range or None,
            collection_date=collection_date,
            lab_source=candidate.lab_source or None,
            extraction_confidence=candidate.composite_confidence,
            verified_by="pending_user",
        )
        container.biomarker_repo.add(record)
        stats["pending_taxonomy"] += 1
        return

    # Unit conversion
    canonical_value: float | None = None
    canonical_unit: str | None = None
    try:
        conv = convert(canonical_id, candidate.raw_value, candidate.raw_unit or None)
        canonical_value = conv.canonical_value
        canonical_unit = conv.canonical_unit
    except (UnitConversionError, UnitMissingError, ValueError) as exc:
        _log.warning("unit conversion skipped for %r: %s", canonical_id, exc)

    # Physiological range check (log only — never block persistence)
    if canonical_value is not None:
        try:
            validate_physiological_range(canonical_id, canonical_value)
        except Exception as exc:  # noqa: BLE001
            _log.warning("range check warning for %r: %s", canonical_id, exc)

    # Duplicate detection (skip persisting if exact duplicate)
    if canonical_value is not None and collection_date is not None:
        dup = container.dedup.check(
            patient_id, canonical_id, collection_date, canonical_value, new_id
        )
        if dup.status == "duplicate":
            stats["duplicate_skipped"] += 1
            return

    verified_by: VerifiedBy = "auto" if candidate.band == Band.AUTO_ACCEPT else "pending_user"
    record = BiomarkerRecordCreate(
        patient_id=patient_id,
        document_id=doc_id,
        canonical_biomarker_id=canonical_id,
        original_name=candidate.raw_name,
        original_value=candidate.raw_value,
        original_unit=candidate.raw_unit or None,
        original_range=candidate.raw_reference_range or None,
        canonical_value=canonical_value,
        canonical_unit=canonical_unit,
        collection_date=collection_date,
        lab_source=candidate.lab_source or None,
        extraction_confidence=candidate.composite_confidence,
        verified_by=verified_by,
    )
    container.biomarker_repo.add(record)

    if candidate.band == Band.AUTO_ACCEPT:
        stats["auto_accepted"] += 1
    else:
        stats["pending_user"] += 1
