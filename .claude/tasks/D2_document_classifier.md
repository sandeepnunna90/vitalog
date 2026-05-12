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

_(append after work is done)_
