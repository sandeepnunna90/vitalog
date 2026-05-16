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

### Implementation (2026-05-15)

**Files created:**
- `src/ingestion/errors.py` — `IngestionError` base + three subtypes: `UnsupportedFormatError(detected_mime)`, `FileTooLargeError(size_bytes, max_bytes)`, `CorruptOrEmptyError(reason)`. Each stores structured attributes alongside the human-readable message. `LowResolutionWarning` is a `str | None` field on `ValidatedUpload`, not an exception.
- `src/ingestion/probes.py` — `probe_pdf(file_bytes) -> bool` (deferred `import fitz`; iterates pages, returns True on first non-empty `get_text()`; always closes doc in `finally`). `probe_image(file_bytes, mime) -> str | None` (deferred PIL import; registers `pillow_heif` opener for HEIC before `Image.open()`; returns warning string if `width < 600 or height < 600`, else `None`).
- `src/ingestion/upload_validator.py` — `ValidatedUpload` Pydantic model (`strict=True`) with 5 fields. `_detect_mime()` uses `puremagic` with a raw-byte HEIC fallback: checks `file_bytes[4:8] == b"ftyp"` then `file_bytes[8:12] in _HEIC_BRANDS` (frozenset of 5 brand codes) to avoid misidentifying MP4/M4A. `UploadValidator.validate()` uses `try/except/finally` so audit log fires on both pass and fail. `_check_integrity()` registers `pillow_heif` opener before `Image.open()` for HEIC (separate from `probe_image`).
- `tests/ingestion/conftest.py` — 10 programmatic fixtures (no committed binaries): `text_pdf_bytes` (reportlab), `image_pdf_bytes` (reportlab + embedded PNG), `high_res_jpeg_bytes` (800×800), `low_res_jpeg_bytes` (400×400), `high_res_png_bytes` (1000×1000), `corrupt_pdf_bytes`, `corrupt_image_bytes`, `empty_bytes`, `docx_bytes` (PK magic bytes), `oversized_pdf_bytes`.
- `tests/ingestion/test_upload_validator.py` — 20 tests covering AC1–AC6 + audit behaviour (fires on pass, fires on fail, swallows audit exceptions, works with `audit_repo=None`).
- `tests/ingestion/test_probes.py` — 8 tests for `probe_pdf` (text → True, image-only → False) and `probe_image` (high-res → None, low-res → warning with dimensions, exactly 600×600 → None, width-only small → warning, height-only small → warning).

**Files modified:**
- `pyproject.toml` — added `pymupdf>=1.24.0`, `puremagic>=1.28`, `pillow>=10.0.0`, `pillow-heif>=0.18.0` to `dependencies`.
- `mypy.ini` — added `[mypy-fitz]`, `[mypy-puremagic]`, `[mypy-PIL.*]`, `[mypy-pillow_heif]` with `ignore_missing_imports = True`.
- `src/ingestion/__init__.py` — exports `UploadValidator`, `ValidatedUpload`, all three error classes, `probe_pdf`, `probe_image`.

**PR review fixes:**
- Removed unused `PIL.UnidentifiedImageError` import (F401) — broad `except Exception` covers all image parse failures.
- Removed redundant `# type: ignore[import-untyped]` inline comments (mypy `unused-ignore`) — mypy.ini stubs already silence those modules.
- Added `safe_filename` sanitisation in `validate()`: `filename[:255].encode("utf-8", errors="replace").decode("utf-8")` before storing in audit log payload.

**Key design decisions:**
- Deferred imports (`fitz`, `PIL`) inside function bodies so `import probes` never fails in envs missing optional deps.
- `PIL.Image.verify()` closes the file handle — `probe_image` opens a fresh `BytesIO` handle separately from `_check_integrity`.
- `pillow_heif.register_heif_opener()` called in both `_check_integrity` and `probe_image` (registration is idempotent).
- Validation order is strict: empty → MIME detect → MIME support → size → integrity → probes. MIME support check before size prevents wasted integrity work on unsupported types.
