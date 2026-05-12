# F5 — Summary Generator (cardiology, first-visit, Mode A)

**Epic:** Intelligence
**Points:** 8
**Priority:** Critical
**Depends on:** B1, B2, B3, B4, A3, A2
**Architecture refs:** §5.4.4; PRD v2 Appointment Prep Summary generation; demo hero flow

## User story

As Mark walking into a cardiology first-visit on Friday,
I want a one-page appointment summary covering my conditions, medications, relevant cardiac biomarkers, trends, data gaps, my notes, and questions to ask — with every number traced to a stored record,
So that I can hand the cardiologist a structured artifact they can actually use, and trust that nothing in it is invented.

## Why this matters

This is the demo's terminal scene and the product's core value proposition. Mode A (B4) is the binding safety constraint — no number reaches the cardiologist without deterministic provenance. The §5.4.4 design choices (sections, no diagnostic language, disclaimer) all converge here.

## Acceptance criteria

1. **Given** Mark's patient profile + cardiology specialist + first-visit type, **When** `SummaryGenerator.generate(patient_id, "cardiology", "first_visit")` runs, **Then** a structured summary is produced with these sections in order: conditions, medications, key results (lipid panel, BP, HbA1c, eGFR, hsCRP), trends (HbA1c + BP if available), data gaps, patient notes (empty initially), questions (empty initially), disclaimer.
2. **Given** every numeric in the generated summary, **When** Mode A runs, **Then** each numeric is wrapped in a structured `Citation{value, unit, collection_date, source_record_id}` and verifies against the retrieval set — any failure rejects the entire generation atomically.
3. **Given** the prompt's hard constraint, **When** the model is tempted to write "you should consider…" or "this indicates…", **Then** L3 banned-phrase regex catches it, retry happens, and persistent failure returns a safe refusal.
4. **Given** a data gap (e.g., no post-statin lipid panel), **When** the summary runs, **Then** the data_gaps section names the missing test explicitly: "No lipid panel collected since starting statin (2026-02-01)."
5. **Given** a derived statement like "HbA1c improved by 0.4% over six months", **When** Mode A runs, **Then** both endpoint records are cited; the arithmetic itself is not independently verified (acknowledged limitation, §12).
6. **Given** the disclaimer requirement, **When** any summary is generated, **Then** the disclaimer from PRD v2 §Compliance is present verbatim in the output: "This summary was prepared by Vitalog from patient-uploaded records. It is not a medical document and does not constitute medical advice. Please verify all information with your healthcare provider."
7. **Given** the audit log, **When** a summary is generated, **Then** event_type `summary_generated` is logged with patient_id, specialist, visit_type, prompt_version, citation_count.

## Files to create / modify

- `src/intelligence/summary_generator.py`
- `src/intelligence/summary_schemas.py` — `Summary` Pydantic model with sections, citations, disclaimer
- `src/intelligence/summary_retrieval.py` — pulls relevant records per specialist + visit type via the specialist content template
- `prompts/summary/cardiology_first_visit_v1.md`
- `prompts/summary/cardiology_first_visit_v1.frontmatter.yaml`
- `prompts/_shared/cardiology_few_shots.md` — specialist-specific few-shots
- `tests/intelligence/test_summary_generator.py` — fixture-driven
- `tests/intelligence/test_summary_constraints.py` — adversarial cardiology probes

## Implementation notes

- Cardiology + first-visit is the ONLY combination implemented for capstone (architecture §11 capstone scope; specialist count is 1–2). The template is structured so adding endocrinology or primary-care for v1 is additive.
- Retrieval set composition: patient profile (conditions, meds, allergies) + the specialist content template's biomarker list, fetched from `BiomarkerRepository` and shaped per the template's section order.
- The prompt uses Claude tool-use to force a structured output (per Mode A spec). Every numeric value MUST be inside a citation tool call — non-citation numerics in the prose fail validation.
- "Data gaps" detection is partly deterministic (the specialist template says "this section needs a lipid panel" — check if one exists) and partly prompted (the model identifies date-relative gaps like "no lipid panel since statin start").
- "Questions" section is intentionally empty in the generated output — Mark fills it via the annotation flow (F6). The model is told NOT to invent questions for the patient.
- Layer stack: L1 → L2 → model → L3 (schema → banned-phrase → Mode A). Each gate is independent. Mode A is the last and strongest.
- Cost: this is the most expensive call in the system. Budget ~$0.05 per generation; track in eval_log.

## Verification

- `pytest tests/intelligence/test_summary_generator.py -q` — covers happy path, forced citation mismatch (Mode A rejects), banned-phrase regression, missing-data graceful behavior
- `pytest tests/intelligence/test_summary_constraints.py -q` — cardiology-specific adversarial probes
- After C4 + H1 land: full demo dry-run, generate summary for Mark's hero data, eyeball-check every numeric matches a record, confirm disclaimer present
- Integration: `pytest -m integration tests/intelligence/test_summary_end_to_end.py`

## INVEST check

- [x] Independent — needs B1, B2, B3, B4, A3, A2 (lots of dependencies because the summary is the integration point — that's expected for the hero feature)
- [x] Negotiable — section order, prompt wording flexible
- [x] Valuable — the demo's terminal scene
- [x] Estimable — well-bounded (large)
- [x] Small — 8 pts (at the limit; do NOT split further or Mode A wiring becomes fragile)
- [x] Testable — fixture + integration

## Deferred (explicitly out of this story)

- Endocrinology, primary care, internal medicine specialist coverage — v1
- Follow-up delta summaries ("what changed since last visit") — v1
- Arithmetic verification of derived values — v1 (architecture §12 limitation 11)
- LLM-as-judge layer on summaries — v1 (architecture §12 limitation 14)
- Smart "questions" generation — v1 (currently patient-authored only)

## Notes / changelog

_(append after work is done)_
