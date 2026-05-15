"""Vitalog persistence layer.

All database and storage operations go through the repositories exported here.
No supabase symbols appear in this module's public interface — consumers work
with Pydantic models only.

Usage (service-role, for admin ops):
    from src.persistence import BiomarkerRepository, get_service_client
    repo = BiomarkerRepository(get_service_client())

Usage (patient JWT, for app code):
    from src.persistence import BiomarkerRepository, get_anon_client
    repo = BiomarkerRepository(get_anon_client(patient_jwt))
"""

from src.persistence.audit_log_repository import AuditLogRepository
from src.persistence.biomarker_repository import BiomarkerRepository
from src.persistence.document_repository import DocumentRepository
from src.persistence.document_store import DocumentStore
from src.persistence.models import (
    AuditLogCreate,
    AuditLogRow,
    BiomarkerRecordCreate,
    BiomarkerRecordRow,
    CanonicalBiomarkerRow,
    DocumentClassification,
    DocumentCreate,
    DocumentRow,
    PatientCreate,
    PatientProfileCreate,
    PatientProfileRow,
    PatientRow,
    PendingStatus,
    PendingTaxonomyEntryCreate,
    PendingTaxonomyEntryRow,
    RetentionPolicy,
    SummaryCreate,
    SummaryRow,
    VerifiedBy,
)
from src.persistence.summary_repository import SummaryRepository
from src.persistence.supabase_client import get_anon_client, get_service_client
from src.persistence.taxonomy_repository import TaxonomyRepository

__all__ = [
    # Repositories
    "AuditLogRepository",
    "BiomarkerRepository",
    "DocumentRepository",
    "DocumentStore",
    "SummaryRepository",
    "TaxonomyRepository",
    # Client factories
    "get_anon_client",
    "get_service_client",
    # Models
    "AuditLogCreate",
    "AuditLogRow",
    "BiomarkerRecordCreate",
    "BiomarkerRecordRow",
    "CanonicalBiomarkerRow",
    "DocumentClassification",
    "DocumentCreate",
    "DocumentRow",
    "PatientCreate",
    "PatientProfileCreate",
    "PatientProfileRow",
    "PatientRow",
    "PendingStatus",
    "PendingTaxonomyEntryCreate",
    "PendingTaxonomyEntryRow",
    "RetentionPolicy",
    "SummaryCreate",
    "SummaryRow",
    "VerifiedBy",
]
