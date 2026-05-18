# F5 — Summary Generator (Mode A)

**Epic:** Intelligence
**Points:** 8
**Priority:** Critical
**Depends on:** B1, B2, B3, B4, A3, A2
**Architecture refs:** §5.4.4; PRD v2 Appointment Prep Summary generation; demo hero flow

## User story

As Mark preparing for an upcoming appointment,
I want a one-page health summary covering my conditions, medications, all available biomarker results, trends, data gaps, and my notes — with every number traced to a stored record,
So that I can hand any specialist a structured artifact they can use, and trust that nothing in it is invented.

## Why this matters

This is the demo's terminal scene and the product's core value proposition. Mode A (B4) is the binding safety constraint — no number reaches the summary without deterministic provenance. Vitalog is a health data organiser, not a clinical decision support system — the summary presents what the patient has, not what a specialist needs.

## Design decisions (from pre-implementation discussion)

- **No specialist or visit-type parameters.** `generate(patient_id)` only. Vitalog does not encode which biomarkers a cardiologist vs endocrinologist needs — that is a clinical assertion we have no authority to make. The LLM reasons over all available patient data and the prompt structure guides what to include.
- **Pass all patient records.** No static biomarker pre-selection. Retrieval fetches all records for the patient; the LLM determines relevance guided by the prompt's section structure.
- **`specialist_content_templates.json` removed.** Was encoding clinical assumptions (which biomarkers belong to which specialist) with no defensible authority. Removed entirely.
- **`condition_biomarker_map.json` → renamed `biomarker_groups.json`.** Restructured as a grouping reference only: flat `biomarkers` list per condition, `guideline` citation embedded, no `notes`, no `primary`/`monitoring` split, no `icd10`. Only groups backed by named clinical guidelines are included (see `docs/guideline_citations.md`). Biomarkers explicitly contradicted by guidelines (e.g., ALT/AST for dyslipidemia per 2026 ACC/AHA) are removed.
- **Disclaimer appended deterministically in code.** Not LLM-generated — verbatim, always present, not subject to LLM paraphrasing or omission.

## Acceptance criteria

1. **Given** a patient_id, **When** `SummaryGenerator.generate(patient_id)` runs, **Then** a structured summary is produced with sections covering: active conditions, current medications, all available biomarker results (organised by what data exists, not by specialist template), notable trends where ≥2 data points exist, data gaps (biomarkers in the patient's condition groups with no recorded value), patient notes (empty initially), and disclaimer.
2. **Given** every numeric in the generated summary, **When** Mode A runs, **Then** each numeric is wrapped in a structured `Citation{value, unit, collection_date, source_record_id}` and verified against the retrieval set — any unverified numeric rejects the entire generation atomically.
3. **Given** the prompt's hard constraint, **When** the model is tempted to write "you should consider…" or "this indicates…", **Then** L3 banned-phrase regex catches it, retry happens with the offending phrase named in the retry prompt, and persistent failure returns a safe refusal.
4. **Given** a data gap (e.g., no lipid panel recorded), **When** the summary runs, **Then** the data_gaps section names it explicitly: "No lipid panel on record."
5. **Given** a derived statement like "HbA1c improved by 0.4% over six months", **When** Mode A runs, **Then** both endpoint records are cited; the arithmetic itself is not independently verified (acknowledged limitation, §12).
6. **Given** any generated summary, **When** the method returns, **Then** the following disclaimer is appended verbatim by the code (not the LLM): "This summary was prepared by Vitalog from patient-uploaded records. It is not a medical document and does not constitute medical advice. Please verify all information with your healthcare provider."
7. **Given** the audit log, **When** a summary is generated, **Then** event_type `summary_generated` is logged with patient_id, prompt_version, citation_count.
8. **Given** `reference_data/biomarker_groups.json`, **When** I read it, **Then** each condition entry has: `display_name`, `guideline` (name, organization, year, url), and a flat `biomarkers` list — no `notes`, no `icd10`, no `primary`/`monitoring` split, and no biomarkers contradicted by the cited guideline.

## Files to create / modify

- `src/intelligence/summary_generator.py` — `generate(patient_id)` signature; fetches all records; calls gateway with Mode A; appends disclaimer field in code after LLM returns
- `src/intelligence/summary_schemas.py` — `Summary` Pydantic model with sections, citations, and a `disclaimer: str` field set by code (not LLM)
- `prompts/summary/v1.md` — generic summary prompt; section structure defined here, not in a JSON template
- `prompts/_registry.yaml` — add `summary@v1` entry
- `reference_data/biomarker_groups.json` — renamed + restructured from `condition_biomarker_map.json`; guideline citations embedded; unsupported biomarkers removed
- `reference_data/specialist_content_templates.json` — **deleted**
- `src/reference_data/__init__.py` — update loader: `load_biomarker_groups()` replaces `load_condition_biomarker_map()`; remove `load_specialist_content_templates()`
- `src/intelligence/retrieval.py` — update `_condition_biomarker_matches` → `_condition_group_matches`; use `load_biomarker_groups()`; F3 NLQ responses that expand via this path must include a disclaimer: "These biomarkers are commonly grouped with [condition] — speak with your provider about what's relevant for you."
- `src/intelligence/context_cards.py` — update import from `load_condition_biomarker_map` → `load_biomarker_groups`
- `tests/intelligence/test_summary_generator.py` — fixture-driven; no API calls
- `tests/intelligence/test_summary_constraints.py` — adversarial probes (banned phrase, citation mismatch, missing data)
- `tests/intelligence/test_summary_end_to_end.py` — integration test, marked `@pytest.mark.integration`
- `docs/guideline_citations.md` — already created; source of truth for which biomarkers are included in `biomarker_groups.json`

## Implementation notes

- The prompt defines the section structure (conditions, medications, results, trends, data gaps, notes). The LLM selects which biomarkers to include in each section based on what records exist — not a pre-selected list.
- "Data gaps" detection: the patient's active conditions from their profile are used to look up `biomarker_groups.json`; any group biomarker with no stored record is named as a gap.
- "Questions" and "patient notes" sections are always empty in generated output — filled via annotation flow (F6). The prompt explicitly instructs the model not to generate questions.
- **Disclaimer field:** `Summary.disclaimer` is a `str` field on the Pydantic model. It is NOT in the prompt or LLM output schema — the generator sets it after the LLM call returns: `summary.disclaimer = DISCLAIMER_TEXT`. The LLM is not asked to produce it and cannot omit or paraphrase it.
- **Retry behavior:** On `BannedPhraseViolation`, retry once with the offending phrase named in the system message. On second failure, return a safe refusal (`SummaryResult` with `error="safe_refusal"`, no summary content). Matches F2 pattern.
- **F3 condition-group disclaimer:** When `_condition_group_matches` in `retrieval.py` expands a query via `biomarker_groups.json`, the NLQ response must include: "These biomarkers are commonly grouped with [condition] based on clinical guidelines — speak with your provider about what's relevant for you." This is appended deterministically, not generated by the LLM.
- Layer stack: L1 → L2 → model → L3 (schema → banned-phrase → Mode A). Mode A is the last and strongest gate.
- Cost: most expensive call in the system. Budget ~$0.05 per generation; tracked in eval_log.
- `biomarker_groups.json` is designed for future migration to a DB table (same as taxonomy). The `guideline` object per condition maps directly to a `guideline_sources` FK column.

## Verification

- `pytest tests/intelligence/test_summary_generator.py -q` — happy path, citation mismatch rejection, banned-phrase regression, missing-data behaviour
- `pytest tests/intelligence/test_summary_constraints.py -q` — adversarial probes
- Manual: generate summary for Mark's hero data after H1 lands; eyeball every numeric against stored records; confirm disclaimer present verbatim
- Integration: `pytest -m integration tests/intelligence/test_summary_end_to_end.py`

## INVEST check

- [x] Independent — needs B1, B2, B3, B4, A3, A2
- [x] Negotiable — section structure and prompt wording flexible
- [x] Valuable — demo's terminal scene
- [x] Estimable — well-bounded (large)
- [x] Small — 8 pts
- [x] Testable — fixture + integration

## Deferred (explicitly out of this story)

- Specialist-specific or visit-type-specific summaries — deliberately not built; design decision, not a deferral
- Follow-up delta summaries ("what changed since last visit") — v1
- Arithmetic verification of derived values — v1 (architecture §12 limitation 11)
- LLM-as-judge layer on summaries — v1 (architecture §12 limitation 14)
- Smart "questions" generation — v1 (currently patient-authored only)
- Background agent to monitor guideline updates and flag stale `biomarker_groups.json` entries — v2 (see roadmap)

## Notes / changelog

### Implementation (2026-05-18)

**Files created:**
- `src/intelligence/summary_generator.py` — `SummaryGenerator.generate(patient_id)` with 2-attempt retry, `_detect_data_gaps()`, `_build_inputs()`, `_convert_citations()`, `_log_audit()`
- `src/intelligence/summary_schemas.py` — `SummaryOutputCitation` (str types for LLM JSON), `SummaryOutput`, `Summary` (disclaimer: str set by code)
- `prompts/summary/v1.md` + `prompts/summary/v2.md` — v2 used in prod (v1 had unescaped `{value:...}` in example block causing KeyError in format_map)
- `tests/intelligence/test_summary_generator.py` — 9 unit tests (happy path, disclaimer, retry, safe-refusal, data gaps, audit)
- `tests/intelligence/test_summary_constraints.py` — 4 Mode A adversarial probes (unknown record_id, ownership leak, unit mismatch, value out of tolerance)
- `tests/intelligence/test_summary_end_to_end.py` — 1 integration test, live API call
- `tests/conftest.py` — `load_dotenv()` so integration tests pick up `.env` credentials
- `reference_data/biomarker_groups.json` — replaces `condition_biomarker_map.json`; 9 conditions, embedded guideline citations, biomarkers contradicted by guidelines removed
- `docs/guideline_citations.md` — source of truth for which biomarkers are in `biomarker_groups.json`

**Files modified:**
- `src/intelligence/retrieval.py` — `ResolveResult` dataclass; `resolve_query()` returns it; `_condition_group_matches` replaces `_condition_biomarker_matches`; imports `load_biomarker_groups`
- `src/intelligence/nlq_handler.py` — unpacks `ResolveResult`; condition-group disclaimer appended in BOTH LLM path and missing-records fallback path
- `src/intelligence/nlq_schemas.py` — added `matched_condition_names: list[str] = []` to `NlqResponse`
- `src/intelligence/context_cards.py` — import `load_biomarker_groups`; reads `groups[c]["display_name"]`
- `src/reference_data/__init__.py` — `load_biomarker_groups()` replaces `load_condition_biomarker_map()` and `load_specialist_templates()`
- `src/reference_data/patient_profile_schemas.py` — comment updated
- `prompts/_registry.yaml` — added summary@v1 and summary@v2 entries
- `tests/intelligence/test_retrieval.py` — all call sites updated for `ResolveResult`
- `tests/intelligence/test_context_cards.py` — updated for `biomarker_groups` structure
- `tests/intelligence/test_nlq_handler.py` — 3 new tests for condition disclaimer paths
- `tests/reference_data/test_loading.py` + `test_patient_profile.py` — updated imports/assertions

**Files deleted:**
- `reference_data/condition_biomarker_map.json` (replaced by `biomarker_groups.json`)
- `reference_data/specialist_content_templates.json` (clinical assumptions with no defensible authority)
- `.claude/tasks/F5_summary_generator_cardiology.md` (superseded by generic design)

**Key design decisions:**
- `SummaryOutputCitation` (str types) + `_convert_citations()` pattern: mirrors `ObservationCitation` from F2; Pydantic strict=True rejects `str→UUID` and `str→date` coercions; ValueError from malformed dates/UUIDs caught in `_attempt()` and triggers retry
- `_PROMPT_VERSION = "v2"`: v1 had unescaped `{value: 6.8, unit: "%"}` in EXAMPLES block, `str.format_map()` interpreted it as a template variable → `KeyError`
- Condition-group disclaimer appended in code (not LLM-generated) in both successful and missing-records paths

**PR:** #29 — all CI checks green, integration test passed against live API (11.86s)
