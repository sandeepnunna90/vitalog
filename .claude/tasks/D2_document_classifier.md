# D2 — Document classifier (3 categories)

**Epic:** Ingestion
**Points:** 5
**Priority:** Critical
**Depends on:** B1, B2
**Architecture refs:** §5.1 (Classification + Document classification subsection); PRD v2 Upload classification row

## User story

As Mark uploading any document to Vitalog,
I want the system to classify it into one of three categories (lab_report / recognized_unsupported / not_supported), with rich subtype data captured for v1,
So that the pipeline either processes it, stores it with a roadmap message, or rejects + discards it — without ever running the expensive parts on the wrong content.

## Why this matters

Classification gates storage (architecture §7.6) AND the rest of the pipeline. Conservative bias means random photos never accumulate as biomarker junk. Three-category routing with rich subtype is the architectural choice that lets v1 grow the routing table without re-prompting (architecture §5.1).

## Acceptance criteria

1. **Given** a clean Quest lab PDF, **When** the classifier runs, **Then** it returns `ClassificationResult(category="lab_report", subtype="lab_panel", confidence≥0.9, reasoning=…)`.
2. **Given** a discharge summary PDF, **When** the classifier runs, **Then** it returns `category="recognized_unsupported"` and `subtype="discharge_summary"` (subtype preserved even though routing collapses).
3. **Given** a personal photo (cat picture), **When** the classifier runs, **Then** it returns `category="not_supported"` with appropriate subtype (e.g., `"personal_photo"`).
4. **Given** any ambiguous content (confidence < 0.7 across categories), **When** the classifier runs, **Then** it returns `not_supported` (conservative bias).
5. **Given** the classifier prompt, **When** I read it, **Then** the prompt is written for the FULL v1 subtype taxonomy (imaging_report, discharge_summary, visit_note, pathology_report, prescription, genetic_test_report, lab_panel, personal_photo, receipt, screenshot, blank, unreadable), even though capstone routes only on the three top-level categories.
6. **Given** the classification result, **When** it flows into the pipeline, **Then** the user-facing message is selected from the templates in §5.1 ("This looks like a {subtype} — …" for recognized_unsupported; generic message for not_supported).

## Files to create / modify

- `src/ingestion/classifier.py` — Gateway-mediated classifier
- `src/ingestion/classification_schemas.py` — `ClassificationResult`, `Category`, `Subtype` enums
- `prompts/classification/v1.md` — the prompt
- `prompts/classification/v1.frontmatter.yaml` — metadata (model, schema, max_tokens)
- `src/ingestion/user_messages.py` — message templates
- `tests/ingestion/test_classifier_unit.py` — uses recorded Gateway responses
- `tests/ingestion/test_classifier_messages.py` — message-template selection

## Implementation notes

- Goes through `Gateway.call("classification", "v1", ...)`. Never call Anthropic directly.
- Classification input: for PDFs, the first page's text (Textract is not used yet — classifier sees rendered text via PyMuPDF). For images, the image itself via vision input (this is the only LLM-vision use outside D5 fallback).
- Conservative bias is encoded in the prompt: "If you are not 95% confident this is a lab report, classify as recognized_unsupported. If you are not 70% confident this is any medical document, classify as not_supported."
- Subtype is preserved in `ClassificationResult` even when routing collapses. Audit log records the subtype.
- The classifier does NOT decide storage — that's D3's job, based on category. Keeps responsibilities clean.
- Cost discipline: classification is one cheap call. Don't make it a multi-step chain.

## Verification

- `pytest tests/ingestion/test_classifier_unit.py -q`
- After C2 lands: run classifier against every doc in `eval_corpus/`, confirm 100% on synthetic, ≥90% on redacted_real, correct categorization on adversarial mixed-content doc
- Manual: feed a deliberately-bad input (blank PDF), observe `not_supported`

## INVEST check

- [x] Independent — only B1 + B2 required
- [x] Negotiable — exact prompt wording flexible
- [x] Valuable — gates storage + pipeline routing
- [x] Estimable — well-bounded
- [x] Small — 5 pts
- [x] Testable — recorded fixtures cover variants

## Deferred (explicitly out of this story)

- Per-subtype routing tables (v1)
- Image content moderation (v1)
- Confidence-based fallback to human review for borderline classifications (v1)

## Notes / changelog

### Implementation (2026-05-15)

**Files created:**
- `src/ingestion/classification_schemas.py` — `Category` + `Subtype` StrEnums (13 subtypes, full v1 taxonomy per AC5); `ClassificationResult` Pydantic model with `Field(ge=0.0, le=1.0)` on `confidence` and `Field(min_length=1)` on `reasoning`.
- `src/ingestion/classifier.py` — `DocumentClassifier` class; `classify()` calls `Gateway.call("classification", "v1", ...)` then applies conservative bias override (confidence < 0.70 → `not_supported`); `_prepare_inputs()` routes PDFs to text extraction and images to base64 vision block; `_extract_pdf_text()` uses early-exit accumulator (stops at `_PDF_TEXT_LIMIT = 8_000` chars); defensive `fitz.open()` try/except returns `""` on failure.
- `src/ingestion/user_messages.py` — `get_user_message()` returns §5.1 message templates; `_SUBTYPE_LABELS` dict covers all 13 subtypes.
- `prompts/classification/v1.md` — classification prompt using `claude-haiku-4-5-20251001`; `max_tokens: 512`; conservative bias rules verbatim in `system_template`; full v1 subtype taxonomy listed in prose (no JSON braces, avoids `format_map` escaping issues).
- `tests/ingestion/test_classifier_unit.py` — 10 tests covering AC1–AC4 and input-path routing (PDF text, blank PDF placeholder, image vision block, gateway call signature).
- `tests/ingestion/test_classifier_messages.py` — 6 tests covering AC6 message templates and exhaustive subtype coverage check.

**Files modified:**
- `prompts/_registry.yaml` — added `classification/v1` entry.
- `src/ingestion/__init__.py` — added exports: `DocumentClassifier`, `ClassificationResult`, `Category`, `Subtype`, `get_user_message`.

**PR review fixes (commit 8f6f581):**
- Added `Field(ge=0.0, le=1.0)` to `confidence` — out-of-range model output now caught at Layer3 schema validation (triggers retry) rather than silently reaching `_apply_conservative_bias`.
- Added `Field(min_length=1)` to `reasoning` — enforces the prompt's stated requirement at the schema level.
- Replaced join-all-then-truncate in `_extract_pdf_text` with early-exit accumulator to avoid large intermediate string allocation for multi-page PDFs.
- Added defensive `fitz.open()` try/except so a corrupt PDF falls through to the `[PDF has no extractable text]` placeholder path instead of raising an untyped exception.

**Key design decisions:**
- `StrEnum` over `(str, Enum)` — Python 3.11+ native, ruff UP042 compliant, enables `category == "lab_report"` comparisons without `.value`.
- Conservative bias is both in the prompt (instructions to the model) and in code (`_apply_conservative_bias`) — double-layer protection; code-side is the hard deterministic safeguard.
- `cast(ClassificationResult, gateway.call(...))` — purely for mypy; Layer3 validates the schema before the cast is reached.
- Model choice: `claude-haiku-4-5-20251001` overrides the gateway default (Sonnet) via the prompt frontmatter `model:` field — classification is a cheap, well-scoped single call.
