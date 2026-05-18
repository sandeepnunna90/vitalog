"""Pydantic models mirroring the Vitalog Supabase schema.

These are the types that cross the repository boundary — inputs and outputs
of every repository method. No supabase SDK types appear here.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

RetentionPolicy = Literal["permanent", "discard_after_classification"]


# ── Base ──────────────────────────────────────────────────────────────────────


class _Base(BaseModel):
    model_config = ConfigDict(strict=True)


# ── Patient ───────────────────────────────────────────────────────────────────


class PatientRow(_Base):
    patient_id: uuid.UUID
    name: str
    dob: date | None
    created_at: datetime


class PatientCreate(_Base):
    patient_id: uuid.UUID
    name: str
    dob: date | None = None


# ── Patient profile ───────────────────────────────────────────────────────────


class PatientProfileRow(_Base):
    patient_id: uuid.UUID
    conditions: list[Any]
    medications: list[Any]
    allergies: list[Any]
    updated_at: datetime


class PatientProfileCreate(_Base):
    patient_id: uuid.UUID
    conditions: list[Any] = []
    medications: list[Any] = []
    allergies: list[Any] = []


# ── Document ──────────────────────────────────────────────────────────────────

DocumentClassification = Literal["lab_report", "recognized_unsupported", "not_supported"]
ProcessingStatus = Literal["pending", "processing", "complete", "failed"]


class DocumentRow(_Base):
    document_id: uuid.UUID
    patient_id: uuid.UUID
    raw_storage_uri: str | None
    classification: DocumentClassification
    uploaded_at: datetime
    processing_status: ProcessingStatus


class DocumentCreate(_Base):
    patient_id: uuid.UUID
    classification: DocumentClassification
    raw_storage_uri: str | None = None
    processing_status: ProcessingStatus = "pending"


# ── Canonical biomarker ───────────────────────────────────────────────────────


class CanonicalBiomarkerRow(_Base):
    vitalog_id: str
    canonical_name: str
    loinc_code: str
    ucum_unit: str
    unit_conversions: list[Any]
    aliases: list[Any]
    conditions: list[Any]
    guideline_ranges: dict[str, Any]
    guideline_citations: dict[str, Any]
    verification_tier: str
    verified: bool
    created_at: datetime
    updated_at: datetime


# ── Pending taxonomy entry ────────────────────────────────────────────────────

PendingStatus = Literal["pending", "confirmed", "rejected", "merged"]


class PendingTaxonomyEntryRow(_Base):
    pending_id: uuid.UUID
    document_id: uuid.UUID | None
    raw_name: str
    raw_unit: str | None
    candidate_loinc_codes: list[Any]
    proposed_canonical_name: str | None
    similarity_to_existing: dict[str, Any]
    status: PendingStatus
    resolved_at: datetime | None
    resolved_by: str | None


class PendingTaxonomyEntryCreate(_Base):
    document_id: uuid.UUID | None = None
    raw_name: str
    raw_unit: str | None = None
    candidate_loinc_codes: list[Any] = []
    proposed_canonical_name: str | None = None
    similarity_to_existing: dict[str, Any] = {}


# ── Biomarker record ──────────────────────────────────────────────────────────

VerifiedBy = Literal["auto", "user", "admin", "pending_user"]


class BiomarkerRecordRow(_Base):
    record_id: uuid.UUID
    patient_id: uuid.UUID
    document_id: uuid.UUID | None
    canonical_biomarker_id: str | None
    pending_taxonomy_id: uuid.UUID | None
    original_name: str
    original_value: str
    original_unit: str | None
    original_range: str | None
    canonical_value: float | None
    canonical_unit: str | None
    collection_date: date | None
    lab_source: str | None
    extraction_confidence: float | None
    verified_by: VerifiedBy
    created_at: datetime


class BiomarkerRecordCreate(_Base):
    patient_id: uuid.UUID
    document_id: uuid.UUID | None = None
    canonical_biomarker_id: str | None = None
    pending_taxonomy_id: uuid.UUID | None = None
    original_name: str
    original_value: str
    original_unit: str | None = None
    original_range: str | None = None
    canonical_value: float | None = None
    canonical_unit: str | None = None
    collection_date: date | None = None
    lab_source: str | None = None
    extraction_confidence: float | None = None
    verified_by: VerifiedBy = "pending_user"


# ── Summary ───────────────────────────────────────────────────────────────────


class SummaryRow(_Base):
    summary_id: uuid.UUID
    patient_id: uuid.UUID
    generated_at: datetime
    content_json: dict[str, Any]
    patient_annotations: str | None
    exported_formats: list[Any]


class SummaryCreate(_Base):
    patient_id: uuid.UUID
    content_json: dict[str, Any]
    patient_annotations: str | None = None
    exported_formats: list[Any] = []


# ── Audit log ─────────────────────────────────────────────────────────────────


class AuditLogRow(_Base):
    log_id: int
    timestamp: datetime
    actor: str
    event_type: str
    payload: dict[str, Any]
    prev_hash: str
    payload_hash: str
    chain_hash: str


class AuditLogCreate(_Base):
    """Only these three fields are supplied by the caller; the DB trigger fills the hashes."""

    actor: str
    event_type: str
    payload: dict[str, Any]
