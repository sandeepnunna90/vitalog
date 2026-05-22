---
title: "Collection Date Extraction Fix"
epic: Ingestion
priority: Critical
created: 2026-05-19
---

# Collection Date Extraction Fix

## Problem Summary

`_normalize_and_persist()` in `src/orchestration/workflows.py` parses
`candidate.collection_date` exclusively via `date.fromisoformat()`. LabCorp
reports cause the LLM structurer to emit dates in `MM/DD/YYYY` format (e.g.,
`06/05/2019`) rather than ISO 8601 (`YYYY-MM-DD`). `fromisoformat()` raises
`ValueError` on these strings, the warning is logged, and `collection_date` is
written to the database as NULL.

Because `src/intelligence/summary_generator.py` filters accepted records by
`r.collection_date is not None`, every record with a NULL date is excluded from
summaries, producing "No accepted biomarker records found."

## Fix Approach

Two-part fix, independent and additive:

### Part 1 — Flexible date parser in `_normalize_and_persist`
When `fromisoformat()` fails, use `dateutil.parser.parse()` which handles
`MM/DD/YYYY`, `June 5 2019`, `05-Jun-19`, `2019.06.05`, and any other format
the LLM might emit. `dayfirst=False` enforces US month-first interpretation.
The ISO path remains attempt #1 (fastest, correct when LLM behaves).

### Part 2 — Document-level regex date extractor
A new module `src/ingestion/date_extractor.py` extracts the collection date from
the raw PDF text using regex patterns keyed on standard lab report header labels.
Independent of the LLM. All candidates from the same upload share the result as a
document-level fallback.

Full PDF text is extracted with PyMuPDF (reads all pages, not just page 1).
For non-PDF uploads, concatenate TextractResult block texts.

## Constraints

- No changes to structurer schema, prompt, or version — LLM is not re-prompted.
- No changes to `summary_generator.py` — the `collection_date is not None` filter
  is correct; fix the data, not the filter.
- `_extract_full_text()` must never raise; return empty string on any failure.
- Existing ISO path is attempt #1; MM/DD/YYYY is attempt #2; document-level date
  is attempt #3 (only when per-candidate date is absent after both).

---

## File 1: `src/ingestion/date_extractor.py` (NEW)

Single public function: `extract_collection_date(text: str) -> date | None`

Regex patterns (in priority order, all case-insensitive):

| Priority | Label | Example |
|---|---|---|
| 1 | `Date collected:` | LabCorp header |
| 2 | `Collection Date:` | generic |
| 3 | `Date of Service:` | billing / DOS |
| 4 | `Specimen Collected:` | Quest variant |
| 5 | `Collected:` | Quest short label |

Each pattern captures `MM/DD/YYYY` or `YYYY-MM-DD`. For the first match, try
`date.fromisoformat()` then `datetime.strptime(s, "%m/%d/%Y").date()`. Return
`None` if nothing matches.

## File 2: `src/orchestration/workflows.py` (MODIFY)

1. Add import: `from src.ingestion.date_extractor import extract_collection_date`
2. Add `from datetime import date, datetime` (extend existing import)
3. New private helper `_extract_full_text(upload, textract_result) -> str`:
   - PDF: PyMuPDF all-page text extraction; broad try/except → return `""` on failure
   - Non-PDF: join `block.text for block in textract_result.blocks`
4. After structurer call, insert:
   ```python
   _full_text = _extract_full_text(upload, textract_result)
   document_date: date | None = extract_collection_date(_full_text)
   ```
5. Thread `document_date` into `_normalize_and_persist` call in the loop
6. Update `_normalize_and_persist` signature:
   ```python
   def _normalize_and_persist(..., document_date: date | None = None) -> None:
   ```
7. Replace date-parsing block:
   ```python
   collection_date: date | None = None
   if candidate.collection_date:
       try:
           collection_date = date.fromisoformat(candidate.collection_date)
       except ValueError:
           try:
               collection_date = datetime.strptime(
                   candidate.collection_date, "%m/%d/%Y"
               ).date()
           except ValueError:
               _log.warning("non-ISO collection_date skipped: %r", candidate.collection_date)
   # Attempt #3: document-level date from raw text
   if collection_date is None and document_date is not None:
       collection_date = document_date
   ```

## File 3: `tests/ingestion/test_date_extractor.py` (NEW)

10 unit tests, no fixtures, no mocks:

| Test | Input | Expected |
|---|---|---|
| `test_labcorp_date_collected` | `"Date collected: 06/05/2019\nHbA1c: 6.8%"` | `date(2019, 6, 5)` |
| `test_collection_date_label` | `"Collection Date: 12/31/2023"` | `date(2023, 12, 31)` |
| `test_date_of_service_label` | `"Date of Service: 01/15/2022"` | `date(2022, 1, 15)` |
| `test_specimen_collected_label` | `"Specimen Collected: 07/04/2021"` | `date(2021, 7, 4)` |
| `test_collected_short_label` | `"Collected: 03/22/2020"` | `date(2020, 3, 22)` |
| `test_iso_format_after_label` | `"Collection Date: 2019-06-05"` | `date(2019, 6, 5)` |
| `test_case_insensitive_label` | `"DATE COLLECTED: 06/05/2019"` | `date(2019, 6, 5)` |
| `test_empty_string` | `""` | `None` |
| `test_no_date_found` | `"HbA1c: 6.8 %\nLDL: 110 mg/dL"` | `None` |
| `test_priority_first_label_wins` | lower-priority label textually first, higher-priority second | date from higher-priority label |

## Implementation Sequence

1. Create `src/ingestion/date_extractor.py` → `make lint && make typecheck`
2. Create `tests/ingestion/test_date_extractor.py` → `uv run pytest tests/ingestion/test_date_extractor.py -q`
3. Modify `src/orchestration/workflows.py` → `make lint && make typecheck`
4. `uv run pytest -q` — full suite must pass

## Key Design Decisions

- **ISO path remains #1** — the LLM is instructed to emit ISO 8601; the MM/DD/YYYY
  fallback is a safety net, not the primary path.
- **Document-level date is last resort** — per-candidate LLM date is more precise
  for multi-draw reports (different dates per candidate). Document-level gives one
  date for the whole document; use only when LLM fails.
- **PyMuPDF over Textract blocks for PDFs** — Textract omits header/footer text
  where collection-date labels appear. PyMuPDF `page.get_text()` reads the full
  text layer including headers.
- **`document_date` defaults to `None`** — backward-compatible; tests that call
  `_normalize_and_persist` directly will continue to work.
