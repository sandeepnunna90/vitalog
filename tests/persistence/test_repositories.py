"""Integration tests for persistence repositories — AC1, AC3, AC4, AC5.

Requires live Supabase credentials:
  SUPABASE_URL, SUPABASE_SERVICE_KEY

Run with: pytest -m integration tests/persistence/test_repositories.py -q
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import date
from typing import Any

import pytest

from src.persistence import (
    AuditLogRepository,
    BiomarkerRecordCreate,
    BiomarkerRepository,
    DocumentCreate,
    DocumentRepository,
    DocumentStore,
    PendingTaxonomyEntryCreate,
    SummaryCreate,
    SummaryRepository,
    TaxonomyRepository,
    get_service_client,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def svc() -> Any:
    """Service-role Supabase client (bypasses RLS)."""
    return get_service_client()


@pytest.fixture()
def patient_id(svc):  # type: ignore[no-untyped-def]
    """Create a throwaway patient row, yield its UUID, then clean up."""
    pid = uuid.uuid4()
    svc.table("patient").insert({"patient_id": str(pid), "name": "Test Patient"}).execute()
    yield pid
    svc.table("patient").delete().eq("patient_id", str(pid)).execute()


@pytest.fixture()
def document_id(svc, patient_id):  # type: ignore[no-untyped-def]
    """Create a throwaway document for the test patient."""
    repo = DocumentRepository(svc)
    doc = repo.add(DocumentCreate(patient_id=patient_id, classification="lab_report"))
    yield doc.document_id
    # Cascade delete via patient cleanup; nothing extra needed.


# ── BiomarkerRepository ───────────────────────────────────────────────────────


@pytest.mark.integration
def test_biomarker_add_and_get(svc, patient_id):  # type: ignore[no-untyped-def]
    repo = BiomarkerRepository(svc)
    create = BiomarkerRecordCreate(
        patient_id=patient_id,
        original_name="HbA1c",
        original_value="6.8",
        original_unit="%",
        canonical_biomarker_id="hba1c",
        canonical_value=6.8,
        canonical_unit="%",
        collection_date=date(2024, 1, 15),
        verified_by="auto",
    )
    added = repo.add(create)
    assert added.record_id is not None
    assert added.original_name == "HbA1c"

    fetched = repo.get(added.record_id)
    assert fetched is not None
    assert fetched.record_id == added.record_id
    assert fetched.canonical_value == pytest.approx(6.8)


@pytest.mark.integration
def test_biomarker_list_for_patient(svc, patient_id):  # type: ignore[no-untyped-def]
    repo = BiomarkerRepository(svc)
    repo.add(
        BiomarkerRecordCreate(patient_id=patient_id, original_name="LDL", original_value="110")
    )
    repo.add(BiomarkerRecordCreate(patient_id=patient_id, original_name="HDL", original_value="55"))

    other_patient = uuid.uuid4()
    svc.table("patient").insert({"patient_id": str(other_patient), "name": "Other"}).execute()
    try:
        repo.add(
            BiomarkerRecordCreate(
                patient_id=other_patient, original_name="TSH", original_value="2.1"
            )
        )
        results = repo.list_for_patient(patient_id)
        names = {r.original_name for r in results}
        assert "LDL" in names
        assert "HDL" in names
        assert "TSH" not in names
    finally:
        svc.table("patient").delete().eq("patient_id", str(other_patient)).execute()


@pytest.mark.integration
def test_biomarker_find_by_canonical_id(svc, patient_id):  # type: ignore[no-untyped-def]
    repo = BiomarkerRepository(svc)
    repo.add(
        BiomarkerRecordCreate(
            patient_id=patient_id,
            original_name="HbA1c",
            original_value="7.2",
            canonical_biomarker_id="hba1c",
            collection_date=date(2023, 6, 1),
        )
    )
    repo.add(
        BiomarkerRecordCreate(
            patient_id=patient_id,
            original_name="HbA1c",
            original_value="6.8",
            canonical_biomarker_id="hba1c",
            collection_date=date(2024, 1, 1),
        )
    )
    results = repo.find_by_canonical_id(patient_id, "hba1c")
    assert len(results) >= 2
    assert all(r.canonical_biomarker_id == "hba1c" for r in results)


@pytest.mark.integration
def test_biomarker_list_pending_user(svc, patient_id):  # type: ignore[no-untyped-def]
    repo = BiomarkerRepository(svc)
    repo.add(
        BiomarkerRecordCreate(
            patient_id=patient_id,
            original_name="Unknown Marker",
            original_value="42",
            verified_by="pending_user",
        )
    )
    repo.add(
        BiomarkerRecordCreate(
            patient_id=patient_id, original_name="HbA1c", original_value="6.8", verified_by="auto"
        )
    )
    pending = repo.list_pending_user(patient_id)
    assert all(r.verified_by == "pending_user" for r in pending)
    assert any(r.original_name == "Unknown Marker" for r in pending)


# ── DocumentRepository ────────────────────────────────────────────────────────


@pytest.mark.integration
def test_document_add_and_get(svc, patient_id):  # type: ignore[no-untyped-def]
    repo = DocumentRepository(svc)
    doc = repo.add(
        DocumentCreate(
            patient_id=patient_id,
            classification="lab_report",
            raw_storage_uri="supabase-storage://lab-reports/test/file.pdf",
        )
    )
    assert doc.document_id is not None
    assert doc.classification == "lab_report"

    fetched = repo.get_by_id(doc.document_id)
    assert fetched is not None
    assert fetched.document_id == doc.document_id


@pytest.mark.integration
def test_document_list_for_patient(svc, patient_id):  # type: ignore[no-untyped-def]
    repo = DocumentRepository(svc)
    repo.add(DocumentCreate(patient_id=patient_id, classification="lab_report"))
    repo.add(DocumentCreate(patient_id=patient_id, classification="recognized_unsupported"))
    docs = repo.list_for_patient(patient_id)
    assert len(docs) >= 2


# ── DocumentStore ─────────────────────────────────────────────────────────────


@pytest.mark.integration
def test_document_store_discard_returns_none(svc):  # type: ignore[no-untyped-def]
    store = DocumentStore(svc)
    uri = store.put(b"fake content", "receipt.pdf", uuid.uuid4(), "discard_after_classification")
    assert uri.startswith("discard://")
    result = store.get(uri)
    assert result is None


@pytest.mark.integration
def test_document_store_permanent_put_and_get(svc):  # type: ignore[no-untyped-def]
    store = DocumentStore(svc)
    content = b"PDF content for integration test"
    pid = uuid.uuid4()
    uri = store.put(content, "test_lab.pdf", pid, "permanent")
    assert uri.startswith("supabase-storage://")
    downloaded = store.get(uri)
    assert downloaded == content


# ── AuditLogRepository ────────────────────────────────────────────────────────


@pytest.mark.integration
def test_audit_log_record_and_hash_chain(svc):  # type: ignore[no-untyped-def]
    repo = AuditLogRepository(svc)

    row1 = repo.record("system", "test_event_a", {"key": "value1"})
    row2 = repo.record("system", "test_event_b", {"key": "value2"})
    row3 = repo.record("system", "test_event_c", {"key": "value3"})

    # Verify hash chain: chain_hash = sha256(prev_hash + payload_hash)
    def sha256_hex(data: str) -> str:
        return hashlib.sha256(data.encode()).hexdigest()

    assert row2.prev_hash == row1.chain_hash
    assert row2.chain_hash == sha256_hex(row2.prev_hash + row2.payload_hash)

    assert row3.prev_hash == row2.chain_hash
    assert row3.chain_hash == sha256_hex(row3.prev_hash + row3.payload_hash)


# ── TaxonomyRepository ────────────────────────────────────────────────────────


@pytest.mark.integration
def test_taxonomy_add_and_resolve_pending(svc, document_id):  # type: ignore[no-untyped-def]
    repo = TaxonomyRepository(svc)
    entry = repo.add_pending(
        PendingTaxonomyEntryCreate(
            document_id=document_id,
            raw_name="Hemoglobin A1C",
            raw_unit="%",
            candidate_loinc_codes=["4548-4"],
        )
    )
    assert entry.status == "pending"
    assert entry.raw_name == "Hemoglobin A1C"

    resolved = repo.resolve_pending(entry.pending_id, "confirmed", "admin")
    assert resolved.status == "confirmed"
    assert resolved.resolved_by == "admin"
    assert resolved.resolved_at is not None


# ── SummaryRepository ─────────────────────────────────────────────────────────


@pytest.mark.integration
def test_summary_add_and_update_annotations(svc, patient_id):  # type: ignore[no-untyped-def]
    repo = SummaryRepository(svc)
    summary = repo.add(
        SummaryCreate(
            patient_id=patient_id,
            content_json={"sections": ["lipid_panel", "blood_pressure_trend"]},
        )
    )
    assert summary.summary_id is not None
    assert summary.patient_annotations is None

    updated = repo.update_annotations(summary.summary_id, "Patient noted fatigue since last visit.")
    assert updated.patient_annotations == "Patient noted fatigue since last visit."

    fetched = repo.get(summary.summary_id)
    assert fetched is not None
    assert fetched.patient_annotations == "Patient noted fatigue since last visit."
