# Task 01 — Pydantic schemas

## Context

Every cross-concern boundary in Vitalog is a Pydantic model: ingestion → normalization → persistence → intelligence → MCP all pass typed objects, not dicts. Defining the schemas first prevents drift later. These models also serve as the tool-use schemas for AI Gateway calls.

## Dependencies

- Task 00 (repo bootstrap)

## In scope

All schemas land in `src/schemas/` as one module per aggregate:

- `documents.py`: `RawDocument`, `DocumentMetadata`, `DocumentCategory` enum (`lab_report`, `recognized_unsupported`, `not_supported`), `DocumentSubtype` enum, `ClassificationResult`.
- `extraction.py`: `ExtractionField` (value, unit, raw_text, confidence), `BiomarkerCandidate` (test_name, value, unit, reference_range, collection_date, lab_source, fields with confidences), `ConfidenceBand` enum (`AUTO_ACCEPT`, `REVIEW`, `REJECT`), `RoutingDecision`.
- `biomarkers.py`: `BiomarkerRecord` (canonical_id, raw_name, value, unit, canonical_value, canonical_unit, collection_date, lab_source, document_id, patient_id, verified_by enum, full provenance), `TaxonomyEntry` (vitalog_id, canonical_name, LOINC, UCUM, aliases, condition_mappings, guideline_ranges).
- `citations.py`: `Citation` (value, unit, collection_date, source_record_id), `CitedNumber`.
- `intelligence.py`: `TrendPoint`, `TrendSeries`, `TargetBand`, `Observation`, `SummarySection`, `SummaryDocument`.
- `audit.py`: `AuditEvent` (event_type, actor, patient_id, document_id, payload, timestamp).

Conventions:

- Pydantic v2, `model_config = ConfigDict(extra="forbid", frozen=True)` on every model.
- All datetime fields tz-aware (`datetime` with `UTC`).
- Enums are `str, Enum` subclasses for JSON serialization.
- Use `Annotated[Decimal, Field(...)]` for biomarker values (no `float`).
- Each module ships a one-line docstring.

## Out of scope (deferred)

- ORM models (Supabase types live in `src/persistence/`, task 08).
- FHIR-shaped models (v2).

## Files to create

- `src/schemas/__init__.py` (re-export public models)
- `src/schemas/documents.py`
- `src/schemas/extraction.py`
- `src/schemas/biomarkers.py`
- `src/schemas/citations.py`
- `src/schemas/intelligence.py`
- `src/schemas/audit.py`
- `tests/schemas/test_*.py` — one test file per module; verify required fields, enum values, frozen behavior, JSON round-trip.

## Architecture references

- `docs/Vitalog_architecture.md` §5.1 — Ingestion data shapes
- `docs/Vitalog_architecture.md` §5.2 — Normalization data shapes
- `docs/Vitalog_architecture.md` §5.1.1 — confidence bands
- `docs/Vitalog_architecture.md` §6 — data architecture
- `docs/Vitalog_architecture.md` §7.2.1 — citation shapes (Mode A vs B)
- `docs/Vitalog_PRD_v2.md` §Data Requirements

## Step-by-step

1. Read architecture §5 + §6 + §7.2.1 carefully — every field listed there must appear in a schema.
2. Define enums first (`DocumentCategory`, `ConfidenceBand`, `VerifiedBy`).
3. Build leaf models (`ExtractionField`, `Citation`, `AuditEvent`) before composites.
4. Build aggregates (`BiomarkerRecord`, `ClassificationResult`, `SummaryDocument`).
5. Write tests for each model: construction, validation failures, JSON round-trip.
6. Add a `src/schemas/__init__.py` that re-exports the public surface.

## Acceptance criteria

- [ ] `pytest tests/schemas -q` — all green.
- [ ] `mypy src/schemas --strict` — no errors.
- [ ] Each model uses `extra="forbid"` and `frozen=True`.
- [ ] All numeric biomarker values are `Decimal`, not `float`.
- [ ] All datetimes are tz-aware.
- [ ] `Citation` fields exactly match architecture §7.2.1 Mode A shape.

## Verification

- `pytest tests/schemas -q`
- `python -c "from src.schemas import BiomarkerRecord; print(BiomarkerRecord.model_json_schema())"`
- Manual: open one schema module; check docstring + extra/frozen config present.
