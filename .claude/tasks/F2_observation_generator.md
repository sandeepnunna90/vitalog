# F2 — Observation Generator (Mode B)

**Epic:** Intelligence
**Points:** 5
**Priority:** High
**Depends on:** B1, B3, B5, F1
**Architecture refs:** §5.4.2; PRD v2 Observation generation prompt

## User story

As Mark looking at my HbA1c trend,
I want a 1–3 sentence factual observation alongside the chart (e.g., "Your March result was 6.8%, within the ADA target range for type 2 diabetes"),
So that I can read the chart without medical training and understand what's normal and what's not — without ever being told what to do.

## Why this matters

Observations are the bridge between raw numbers and patient understanding. The hard constraint — facts only, no clinical inference, no cause attribution — is what keeps Vitalog out of the medical-advice business. Mode B verification + L3 banned-phrase regex are what enforce that constraint mechanically.

## Acceptance criteria

1. **Given** a biomarker record + the trend + the published guideline range, **When** `ObservationGenerator.generate(record_id)` runs, **Then** it returns 1–3 sentences of plain-language description that include the value, the published target reference (with source citation), and a factual placement of this value relative to that target.
2. **Given** the prompt's hard constraints, **When** the model is asked something like "is this bad?", **Then** the output never includes "you should", "I recommend", "this means you have", or any phrase from the banned list (caught by L3).
3. **Given** every numeric in the observation, **When** Mode B verifies the output, **Then** every numeric must match a record or a guideline-range bound — unmatched numerics cause rejection.
4. **Given** a published range is referenced (e.g., "ADA target <7.0%"), **When** the observation is generated, **Then** the source citation is embedded in the response object (not just the model's prose) so downstream renderers can show "Source: ADA Standards of Care".
5. **Given** the L3 stack, **When** the model emits a clinical inference like "this trend suggests well-controlled diabetes", **Then** the banned-phrase scanner OR the LLM retries-and-refuses path catches it (the suite from C4 verifies this against adversarial prompts).
6. **Given** the audit log, **When** an observation is generated, **Then** event_type `observation_generated` is logged with the record_id and prompt version.

## Files to create / modify

- `src/intelligence/observation_generator.py`
- `src/intelligence/observation_schemas.py` — `Observation` Pydantic model (text, citations, record_id, prompt_version)
- `prompts/observation/v1.md`
- `prompts/observation/v1.frontmatter.yaml`
- `tests/intelligence/test_observation_generator.py` — uses recorded Gateway responses
- `tests/intelligence/test_observation_constraints.py` — adversarial sub-suite specifically targeting observation generation

## Implementation notes

- Goes through `Gateway.call("observation", "v1", ...)`. Mode B verifier (B5) is wired into the Gateway's L3 stack and runs automatically.
- Retrieval set for Mode B: the single biomarker record + the published range bound(s) for that biomarker. Tight retrieval set means narrower attack surface for hallucination.
- The prompt explicitly forbids: clinical inference, cause attribution, predictions, recommendations. Includes 3+ few-shot examples of correct factual observations.
- Output is structured (tool-use) even though the text is prose: the model emits `{text: "...", citations: [{kind: "record", id: "..."}, {kind: "guideline", source: "ADA", range: "<7.0%"}]}`. This makes citation tracking explicit.
- If Mode B rejects, the safe-refusal output is `"This observation could not be generated for this record. Please review the raw value directly."` — never a partial observation.
- Banned-phrase list from B3 is the FIRST line of defense; Mode B is the SECOND; the prompt's constraints are the third. Three layers, each independent.

## Verification

- `pytest tests/intelligence/test_observation_generator.py -q` — recorded fixtures
- `pytest tests/intelligence/test_observation_constraints.py -q` — covers adversarial-style prompts targeted at observations
- After C4 lands: full adversarial run, observations are one of the 3 outputs checked
- Manual: generate observations for all 9 hero HbA1c records, eyeball-check for tone and factual correctness

## INVEST check

- [x] Independent — B1, B3, B5, F1 contracts required
- [x] Negotiable — exact prompt wording flexible (versioned)
- [x] Valuable — every trend point gets one
- [x] Estimable — well-bounded
- [x] Small — 5 pts
- [x] Testable — fixture + constraints suite

## Deferred (explicitly out of this story)

- Per-condition phrasing variation — v1
- Multi-biomarker observations (e.g., "your HbA1c and fasting glucose tell a consistent story") — v1
- LLM-as-judge layer on observations — v1

## Notes / changelog

### Implementation (2026-05-17)

**Files created:**
- `src/intelligence/observation_schemas.py` — `ObservationCitation`, `ObservationOutput`, `Observation` Pydantic models. Key: `record_id: str | None` (not UUID) because Pydantic strict=True rejects str→UUID coercion from LLM JSON output.
- `src/intelligence/observation_generator.py` — `ObservationGenerator` class with `generate()`, `_attempt()` (retry-then-safe-refusal), `_log_audit()`. Module-level helpers: `_build_retrieval_set`, `_make_guideline_record`, `_build_inputs`.
- `prompts/observation/v1.md` — embedded YAML frontmatter; system template with hard rules + correct/wrong examples (no curly braces to avoid `format_map` conflicts); user template with 6 inputs.
- `tests/intelligence/test_observation_generator.py` — 16 tests, mocking `AnthropicAdapter.call` so L3 runs for real.
- `tests/intelligence/test_observation_constraints.py` — 7 tests for L3 banned-phrase scanner (5 caught, 2 clean).

**Files modified:**
- `prompts/_registry.yaml` — added `observation / v1` entry.

**Key design decisions:**
- Mode B retrieval set includes synthetic `BiomarkerRecordRow` entries for each guideline band bound (`band.lower`, `band.upper`) so "7.0%" from "ADA target <7.0%" doesn't cause a false rejection.
- Date format is month-first ("March 12, 2026") so Mode B's false-positive filter correctly skips the day number.
- `_attempt` catches both `ModeBVerificationError` and `OutputValidationError`, logs a WARNING, returns `None` — two failures in a row yields `_SAFE_REFUSAL`.
- Pending-taxonomy guard raises `ValueError` with "pending-taxonomy" in the message rather than silently passing `""` to `get_trend`.

**PR review fixes (PR #22, commit f0c06ed):**
1. Removed prior-record value from prompt CORRECT example (systematic Mode B rejection risk).
2. Added `_audit_log.warning` in `_attempt` for swallowed exceptions.
3. Added explicit pending-taxonomy guard (was silently passing `or ""`).
4. Corrected prompt doc date format ("Month D, YYYY").
5. Cleaned up `test_generate_record_not_found_raises`; added `test_generate_pending_taxonomy_raises`.
6. Widened `_side_effect(*_args, **_kwargs)` signature in retry test.
