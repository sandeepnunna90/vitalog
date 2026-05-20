# Admin SQL Queries

Run these in the Supabase SQL editor. Replace `<patient_id>` with the actual UUID.

---

## Delete all data for a patient

Deletes all biomarker records, pending taxonomy entries, documents, and summaries
for a patient. Run statements in order — FK constraints require children before parents.

```sql
-- 1. Biomarker records (references document + pending_taxonomy_entry)
DELETE FROM biomarker_record
WHERE document_id IN (
  SELECT document_id FROM document WHERE patient_id = '<your-patient-uuid>'
);

-- 2. Pending taxonomy entries (references document)
DELETE FROM pending_taxonomy_entry
WHERE document_id IN (
  SELECT document_id FROM document WHERE patient_id = '<your-patient-uuid>'
);

-- 3. Documents
DELETE FROM document
WHERE patient_id = '<your-patient-uuid>';

-- 4. Summaries
DELETE FROM summary
WHERE patient_id = '<your-patient-uuid>';
```

---

## List documents for a patient

```sql
SELECT document_id, classification, processing_status, uploaded_at
FROM document
WHERE patient_id = '<your-patient-uuid>'
ORDER BY uploaded_at;
```

## List pending taxonomy entries for a patient

```sql
SELECT p.pending_id, p.raw_name, p.raw_unit, p.status, p.document_id
FROM pending_taxonomy_entry p
JOIN document d ON d.document_id = p.document_id
WHERE d.patient_id = '<your-patient-uuid>'
ORDER BY p.raw_name;
```

## List biomarker records for a patient

```sql
SELECT canonical_biomarker_id, original_name, canonical_value, canonical_unit,
       collection_date, extraction_confidence, verified_by
FROM biomarker_record
WHERE patient_id = '<your-patient-uuid>'
ORDER BY collection_date, canonical_biomarker_id;
```

---

## Known patient IDs

| Patient | ID |
|---|---|
| Your patient (set via `VITALOG_PATIENT_ID` env var) | `<your-patient-uuid>` |
