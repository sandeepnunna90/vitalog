-- Vitalog A3: Initial schema
-- 8 tables + indexes + RLS policies
-- Applies pgcrypto extension used by migration 002.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ── Tables ────────────────────────────────────────────────────────────────────

CREATE TABLE patient (
  patient_id  UUID        PRIMARY KEY,
  name        TEXT        NOT NULL,
  dob         DATE,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE patient_profile (
  patient_id  UUID        PRIMARY KEY REFERENCES patient(patient_id) ON DELETE CASCADE,
  conditions  JSONB       NOT NULL DEFAULT '[]',
  medications JSONB       NOT NULL DEFAULT '[]',
  allergies   JSONB       NOT NULL DEFAULT '[]',
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE document (
  document_id       UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id        UUID        NOT NULL REFERENCES patient(patient_id) ON DELETE CASCADE,
  raw_storage_uri   TEXT,
  classification    TEXT        NOT NULL CHECK (classification IN ('lab_report','recognized_unsupported','not_supported')),
  uploaded_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  processing_status TEXT        NOT NULL DEFAULT 'pending'
);

CREATE TABLE canonical_biomarker (
  vitalog_id          TEXT        PRIMARY KEY,
  canonical_name      TEXT        NOT NULL,
  loinc_code          TEXT        NOT NULL,
  ucum_unit           TEXT        NOT NULL,
  unit_conversions    JSONB       NOT NULL DEFAULT '[]',
  aliases             JSONB       NOT NULL DEFAULT '[]',
  conditions          JSONB       NOT NULL DEFAULT '[]',
  guideline_ranges    JSONB       NOT NULL DEFAULT '{}',
  guideline_citations JSONB       NOT NULL DEFAULT '{}',
  verification_tier   TEXT        NOT NULL DEFAULT 'canonical',
  verified            BOOLEAN     NOT NULL DEFAULT TRUE,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE pending_taxonomy_entry (
  pending_id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id             UUID        REFERENCES document(document_id) ON DELETE SET NULL,
  raw_name                TEXT        NOT NULL,
  raw_unit                TEXT,
  candidate_loinc_codes   JSONB       NOT NULL DEFAULT '[]',
  proposed_canonical_name TEXT,
  similarity_to_existing  JSONB       NOT NULL DEFAULT '{}',
  status                  TEXT        NOT NULL DEFAULT 'pending'
                          CHECK (status IN ('pending','confirmed','rejected','merged')),
  resolved_at             TIMESTAMPTZ,
  resolved_by             TEXT
);

CREATE TABLE biomarker_record (
  record_id              UUID             PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id             UUID             NOT NULL REFERENCES patient(patient_id) ON DELETE CASCADE,
  document_id            UUID             REFERENCES document(document_id) ON DELETE SET NULL,
  canonical_biomarker_id TEXT             REFERENCES canonical_biomarker(vitalog_id),
  pending_taxonomy_id    UUID             REFERENCES pending_taxonomy_entry(pending_id),
  original_name          TEXT             NOT NULL,
  original_value         TEXT             NOT NULL,
  original_unit          TEXT,
  original_range         TEXT,
  canonical_value        DOUBLE PRECISION,
  canonical_unit         TEXT,
  collection_date        DATE,
  lab_source             TEXT,
  extraction_confidence  DOUBLE PRECISION,
  verified_by            TEXT             NOT NULL DEFAULT 'pending_user'
                         CHECK (verified_by IN ('auto','user','admin','pending_user')),
  created_at             TIMESTAMPTZ      NOT NULL DEFAULT now()
);

CREATE TABLE summary (
  summary_id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id          UUID        NOT NULL REFERENCES patient(patient_id) ON DELETE CASCADE,
  specialist_type     TEXT        NOT NULL,
  visit_type          TEXT        NOT NULL,
  generated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  content_json        JSONB       NOT NULL,
  patient_annotations TEXT,
  exported_formats    JSONB       NOT NULL DEFAULT '[]'
);

CREATE TABLE audit_log (
  log_id       BIGSERIAL   PRIMARY KEY,
  timestamp    TIMESTAMPTZ NOT NULL DEFAULT now(),
  actor        TEXT        NOT NULL,
  event_type   TEXT        NOT NULL,
  payload      JSONB       NOT NULL,
  prev_hash    TEXT        NOT NULL DEFAULT '',
  payload_hash TEXT        NOT NULL DEFAULT '',
  chain_hash   TEXT        NOT NULL DEFAULT ''
);

-- ── Indexes ───────────────────────────────────────────────────────────────────

CREATE INDEX idx_document_patient            ON document(patient_id);
CREATE INDEX idx_biomarker_record_patient    ON biomarker_record(patient_id);
CREATE INDEX idx_biomarker_record_canonical  ON biomarker_record(patient_id, canonical_biomarker_id);
CREATE INDEX idx_biomarker_record_date       ON biomarker_record(patient_id, collection_date);
CREATE INDEX idx_summary_patient             ON summary(patient_id);
CREATE INDEX idx_audit_log_actor             ON audit_log(actor);
CREATE INDEX idx_pending_taxonomy_status     ON pending_taxonomy_entry(status);

-- ── Row-Level Security ────────────────────────────────────────────────────────

ALTER TABLE patient               ENABLE ROW LEVEL SECURITY;
ALTER TABLE patient_profile       ENABLE ROW LEVEL SECURITY;
ALTER TABLE document              ENABLE ROW LEVEL SECURITY;
ALTER TABLE biomarker_record      ENABLE ROW LEVEL SECURITY;
ALTER TABLE summary               ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log             ENABLE ROW LEVEL SECURITY;
ALTER TABLE canonical_biomarker   ENABLE ROW LEVEL SECURITY;
ALTER TABLE pending_taxonomy_entry ENABLE ROW LEVEL SECURITY;

-- Patient-scoped tables: all operations scoped to auth.uid()
CREATE POLICY patient_isolation         ON patient          FOR ALL USING (patient_id = auth.uid());
CREATE POLICY patient_profile_isolation ON patient_profile  FOR ALL USING (patient_id = auth.uid());
CREATE POLICY document_isolation        ON document         FOR ALL USING (patient_id = auth.uid());
CREATE POLICY biomarker_record_isolation ON biomarker_record FOR ALL USING (patient_id = auth.uid());
CREATE POLICY summary_isolation         ON summary          FOR ALL USING (patient_id = auth.uid());

-- Audit log: SELECT own rows, INSERT allowed, UPDATE/DELETE implicitly blocked by RLS
CREATE POLICY audit_log_select ON audit_log
  FOR SELECT USING (actor = auth.uid()::text OR actor = 'system');
CREATE POLICY audit_log_insert ON audit_log
  FOR INSERT WITH CHECK (true);

-- Canonical biomarker taxonomy: public read (shared reference data), write via service role only
CREATE POLICY canonical_biomarker_read ON canonical_biomarker
  FOR SELECT USING (true);

-- Pending taxonomy entries: patient sees only entries from their own documents
CREATE POLICY pending_taxonomy_read ON pending_taxonomy_entry
  FOR SELECT USING (
    document_id IN (SELECT document_id FROM document WHERE patient_id = auth.uid())
  );
