# D1 — Upload + validation + pre-LLM probes

**Epic:** Ingestion
**Points:** 3
**Priority:** High
**Depends on:** A3
**Architecture refs:** §5.1 (steps 1–2 of internal pipeline)

## User story

As Mark uploading a lab document,
I want Vitalog to reject obviously-bad files (corrupt, empty, wrong format) before any expensive LLM call,
So that I get a fast, clear error and Vitalog doesn't waste tokens on garbage.

## Why this matters

P4 (determinism wherever possible) — file validation is one of those things. Catching empty/corrupt files at the boundary is cheap and saves a Textract + Anthropic round-trip on every misfire. It also gives the upload tool a stable contract for "what counts as a valid upload."

## Acceptance criteria

1. **Given** an upload of a non-supported MIME (e.g., `.docx`, `.zip`), **When** the validator runs, **Then** the call is rejected with `UnsupportedFormatError` and a user-facing message naming the supported set (`PDF`, `JPG`, `JPEG`, `PNG`, `HEIC`).
2. **Given** an upload exceeding the size cap (configurable, default 20 MB), **When** the validator runs, **Then** `FileTooLargeError` is returned.
3. **Given** an empty file (0 bytes) or a file whose MIME doesn't match its content, **When** the validator runs, **Then** `CorruptOrEmptyError` is returned.
4. **Given** a PDF, **When** the probe runs, **Then** it reports `is_text_extractable: bool` based on whether `PyMuPDF` (or equivalent) can extract any text — used to decide whether vision-fallback is likely to be needed.
5. **Given** an image input, **When** the probe runs, **Then** it reports the resolution; if below 600×600, returns `LowResolutionWarning` (does not reject, but logs).
6. **Given** the contract, **When** the validator passes a file, **Then** it returns a typed `ValidatedUpload(file_bytes, mime, size_bytes, is_text_extractable, resolution_warning)` Pydantic model.

## Files to create / modify

- `src/ingestion/upload_validator.py`
- `src/ingestion/probes.py` — text-extractable probe, resolution probe
- `src/ingestion/errors.py` — typed exceptions
- `src/ingestion/__init__.py`
- `tests/ingestion/test_upload_validator.py`
- `tests/ingestion/test_probes.py`
- `tests/ingestion/fixtures/` — sample files (small PDF, image-only PDF, low-res JPG, empty file)

## Implementation notes

- MIME sniffing uses `python-magic` or `puremagic`; do NOT trust the client-supplied content-type.
- `PyMuPDF` (`pip install pymupdf`) for the text-extractable probe — add to `pyproject.toml`.
- HEIC support: requires `pillow-heif`. If unavailable on the dev machine, document and fall back to "convert to JPEG client-side" — not ideal but acceptable for capstone.
- The validator does NOT classify the document (that's D2); it only checks file health. Conservative classification bias lives in D2.
- Audit log: every upload attempt — passing and failing — writes one audit-log entry with the file's hash, MIME, size, validation_result.

## Verification

- `pytest tests/ingestion/test_upload_validator.py -q`
- `pytest tests/ingestion/test_probes.py -q`
- Manual: upload a known-corrupt PDF, observe rejection + audit entry

## INVEST check

- [x] Independent — only A3 required (for audit log writes)
- [x] Negotiable — exact size cap configurable
- [x] Valuable — gates D2 cleanly; saves cost
- [x] Estimable — well-bounded
- [x] Small — 3 pts
- [x] Testable — fixture-driven

## Deferred (explicitly out of this story)

- Virus scanning (v1.5)
- HEIC fallback conversion service (v1)
- Multi-file upload (capstone is one-at-a-time)

## Notes / changelog

_(append after work is done)_
