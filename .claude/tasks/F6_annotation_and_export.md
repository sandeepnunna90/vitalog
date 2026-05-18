# F6 — Annotation + export (PDF / markdown / JSON)

**Epic:** Intelligence
**Points:** 6
**Priority:** High
**Depends on:** F5, A3
**Architecture refs:** §5.7 (`export_summary`); PRD v2 Appointment Prep Patient annotation + Export rows

## User story

As Mark reviewing the generated summary,
I want to add free-text notes to any section (e.g., "I started a statin on Feb 1"), and export the final document as PDF, markdown, or JSON,
So that I can email a polished PDF to the cardiology office the night before and bring my personal additions along.

## Why this matters

Annotation closes the loop from "system-generated" to "patient-owned". Three export formats serve three audiences: PDF for the doctor, markdown for portability, JSON for re-import. Disclaimer + timestamp on every export keep the safety story intact in the printed artifact.

## Acceptance criteria

1. **Given** a generated summary stored in Supabase, **When** I call `SummaryAnnotator.add_note(summary_id, section, text)`, **Then** the annotation is appended to that section with `is_patient_authored=true` and persisted.
2. **Given** an annotated summary, **When** `export_summary(summary_id, format="pdf")` runs, **Then** a PDF is produced with patient annotations visually distinct from system content (e.g., italic + leading marker "📝 Mark's note:" — emoji acceptable here as a visual cue in the patient-facing artifact, NOT in code).
3. **Given** any export format, **When** the file is produced, **Then** it includes the disclaimer verbatim and a generation timestamp in ISO 8601.
4. **Given** `format="markdown"`, **When** export runs, **Then** the output is GitHub-flavored markdown with section headings, citations rendered as footnote-style references, and patient annotations clearly styled.
5. **Given** `format="json"`, **When** export runs, **Then** the JSON is the structured Summary Pydantic model + annotations, so a future import can round-trip it.
6. **Given** the audit log, **When** any export runs, **Then** event_type `summary_exported` is logged with summary_id, format, byte_size.
7. **Given** the contract, **When** PDF export runs, **Then** rendering uses `reportlab` deterministically — same summary + same annotations produce a byte-equal PDF (modulo timestamp).

## Files to create / modify

- `src/intelligence/annotator.py`
- `src/intelligence/exporter.py` — top-level dispatch
- `src/intelligence/exporters/pdf_exporter.py`
- `src/intelligence/exporters/markdown_exporter.py`
- `src/intelligence/exporters/json_exporter.py`
- `src/persistence/summary_repository.py` — extend with annotation persistence
- `tests/intelligence/test_annotator.py`
- `tests/intelligence/test_exporters.py`

## Implementation notes

- Annotations are stored in the `summary.patient_annotations` JSON column from A3's schema. Each annotation is `{section, text, created_at, annotation_id}`.
- The PDF exporter uses `reportlab`'s `Platypus` flowables. Layout: title block (patient name from profile + visit type + generation timestamp), one paragraph per section, citations as superscript references with a citations list at the bottom, patient annotations inline with their section, disclaimer in the footer of every page.
- Markdown exporter is the simplest of the three; it's the format the founder uses for eval verification.
- JSON exporter emits the Pydantic model verbatim — including all citation metadata. Sufficient for re-import.
- Capstone PDF discipline: no images, no logos, no fancy theming. The artifact's job is clarity, not branding.
- Disclaimer placement: every page of the PDF (footer), top of the markdown, top-level `disclaimer` field in the JSON.

## Verification

- `pytest tests/intelligence/test_annotator.py -q`
- `pytest tests/intelligence/test_exporters.py -q` — covers all 3 formats + annotation rendering
- Manual: end-to-end — generate Mark's cardiology summary, add an annotation ("Started statin 2026-02-01"), export all 3 formats, open each one and confirm shape

## INVEST check

- [x] Independent — F5 + A3 required
- [x] Negotiable — exact PDF layout flexible
- [x] Valuable — the patient-facing artifact
- [x] Estimable — well-bounded
- [x] Small — 6 pts (just under the cap)
- [x] Testable — all three exporters fixture-tested

## Deferred (explicitly out of this story)

- Custom branding / themes — v1 web UI
- Editable summary in place (re-running F5 after edits) — v1
- Encrypted export — v1.5
- Direct email send from Vitalog — likely never (provider-side mail)

## Notes / changelog

### Implementation (2026-05-18)

**Files created:**
- `src/intelligence/export_schemas.py` — `Annotation` Pydantic model; `annotation_id: str` (not UUID) to survive Supabase JSON round-trip under `strict=True`
- `src/intelligence/annotator.py` — `SummaryAnnotator.persist()` (F5 `Summary` → Supabase `SummaryRow`) and `add_note()` (append patient annotation to `patient_annotations` JSON column); `_VALID_SECTIONS` frozenset of 6 valid keys; `summary_persisted` audit event
- `src/intelligence/exporter.py` — `export_summary(summary_id, format, repo)` dispatch to three exporters; `_log_export_audit()` on every call
- `src/intelligence/exporters/__init__.py` — empty package marker
- `src/intelligence/exporters/pdf_exporter.py` — `reportlab.platypus` PDF with `xml.sax.saxutils.escape()` on all LLM/patient text; disclaimer in body and footer
- `src/intelligence/exporters/markdown_exporter.py` — GFM: disclaimer blockquote at top, `## ` section headings, annotation blockquotes, citation footnotes
- `src/intelligence/exporters/json_exporter.py` — merges `content_json` + `summary_id` + `patient_annotations` + `exported_at`
- `migrations/003_summary_specialist_nullable.sql` — `DROP COLUMN specialist_type/visit_type` (columns removed from Python models; schema must match)
- `tests/intelligence/test_annotator.py` — 7 unit tests (persist, add_note, audit event, invalid section, missing summary, preserves existing annotations)
- `tests/intelligence/test_exporters.py` — 8 unit tests (PDF bytes, markdown structure, JSON roundtrip, dispatch, unknown format)

**Files modified:**
- `src/persistence/models.py` — removed `specialist_type` and `visit_type` entirely from `SummaryRow` and `SummaryCreate`
- `src/persistence/summary_repository.py` — `model_validate(data, strict=False)` at all DB parse boundaries
- `src/persistence/biomarker_repository.py` — same `strict=False` fix
- `src/persistence/document_repository.py` — same `strict=False` fix
- `src/persistence/audit_log_repository.py` — same `strict=False` fix
- `src/persistence/taxonomy_repository.py` — same `strict=False` fix
- `tests/persistence/test_repositories.py` — removed stale `specialist_type`/`visit_type` from `SummaryCreate` fixture
- `docs/Vitalog_architecture.md` — removed stale `specialist_type`/`visit_type` from schema and `prepare_summary` signature

**Key design decisions:**
- `Annotation.annotation_id: str` — mirrors `SummaryOutputCitation` pattern; `strict=True` rejects `str→UUID` on Supabase JSON round-trip
- `model_validate(..., strict=False)` at all repository DB boundaries — Supabase returns UUID/datetime as strings; `strict=True` remains for all application code construction paths (same pattern as G2 `load_patient_profile`)
- `xml.sax.saxutils.escape()` on reportlab `Paragraph()` content — reportlab renders as XML; unescaped patient/LLM text can inject markup or raise render exceptions
- Migration 003 updated to `DROP COLUMN` (not just `DROP NOT NULL`) to keep DB schema in sync with Python models

**PR review fixes:**
- Added `summary_persisted` audit event in `persist()` and `test_persist_emits_audit_event` (previously `self._audit` was stored but never called)
- Applied `xml.sax.saxutils.escape()` to both `content` (line 81) and `note_text` (line 83) in `pdf_exporter.py`
- Upgraded migration 003 from `DROP NOT NULL` → `DROP COLUMN IF EXISTS`
- `strict=False` applied to all five persistence repositories (systemic fix for latent Supabase string coercion bug)

**PR:** #30
