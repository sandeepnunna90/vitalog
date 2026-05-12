# Task 12 — Observation Generator + Layer 3 + Mode B verification

## Context

Per architecture §5.4.2, the Observation Generator produces 1 factual sentence per biomarker (capstone-minimum, not the 1–3 sentence richer version). It's the first generator that needs **Layer 3** guardrails wired up: banned-phrase regex, Pydantic schema, and **Mode B citation verification** (parse numeric tokens, match to retrieval set with ±0.5% tolerance, atomic reject on mismatch).

## Dependencies

- Task 02 (Gateway — Layer 3 stub becomes concrete here)
- Task 09 (normalization — retrieval pulls normalized records)
- Task 11 (trend engine — observation is grounded in trend context)

## In scope

`src/intelligence/observation_generator.py`:

- `ObservationGenerator.generate(trend_series) -> Observation`:
  - Pulls latest 1–2 data points from the series for context.
  - Calls Gateway with `prompts/observations/v1.md`.
  - Hard constraints in prompt: 1 factual sentence; no inference, recommendation, cause attribution, prediction; cite the source guideline if a range is mentioned.
  - Tool-use response shape: `Observation(text, cited_values: List[Citation])`.

`src/gateway/guardrails/layer3.py` — concrete validators (replace task 02 stub):

- `SchemaValidator` — checks Pydantic shape (already enforced by tool-use; this is belt-and-suspenders).
- `BannedPhraseValidator` — regex catches `recommend`, `suggest`, `should consider`, `you have`, `you should`, `talk to your doctor about starting`, `your X is high/low`, etc. Banned-phrase list shared with task 15's adversarial suite.
- `CitationVerifierModeB` — per architecture §7.2.1:
  - Parse all numeric tokens from `text` (regex `\d+(\.\d+)?`).
  - For each, check it matches a value in `cited_values` ±0.5% tolerance (for decimals) or exact (for integers).
  - Mismatch → `ValidationResult(passed=False, reason=...)` → Gateway retries up to 2 times → fail-closed.

`prompts/observations/v1.md` — capstone-minimum: 1 sentence per biomarker, factual only, cite guideline if range mentioned.

## Out of scope (deferred)

- Multi-sentence rich observations (v1).
- Cross-biomarker observations (v1 / NLQ task 17).
- LLM-as-judge (architecture §12 — v1).

## Files to create

- `src/intelligence/observation_generator.py`
- `src/gateway/guardrails/layer3.py` (full implementation)
- `src/gateway/guardrails/banned_phrases.py` (the shared list)
- `src/gateway/guardrails/citation_mode_b.py`
- `prompts/observations/v1.md`
- `tests/intelligence/test_observation_generator.py`
- `tests/gateway/test_layer3.py` (extends task 02's stub tests)
- `tests/gateway/test_citation_mode_b.py`

## Architecture references

- `docs/Vitalog_architecture.md` §5.4.2 — Observation Generator
- `docs/Vitalog_architecture.md` §7.2 Layer 3 — schema + regex + citation
- `docs/Vitalog_architecture.md` §7.2.1 — Mode B parse-and-match spec
- `docs/Vitalog_PRD_v2.md` §Prompt Requirements "Observation generation"
- `docs/Vitalog_PRD_v2.md` §Functional Requirements "Safety — Citation Mode B"

## Step-by-step

1. Write `banned_phrases.py` — start with 30+ entries from architecture / PRD examples + own additions.
2. Write `citation_mode_b.py` — numeric extraction + tolerance match (pure function, easy to test).
3. Implement `Layer3Validator` orchestrating Schema + BannedPhrase + CitationModeB.
4. Wire Layer 3 into Gateway (replace stub).
5. Write `prompts/observations/v1.md`.
6. Implement `ObservationGenerator.generate`.
7. Tests: factual output passes; recommendation-style output rejected; hallucinated number rejected.

## Acceptance criteria

- [ ] All adversarial-style outputs trigger banned-phrase rejection.
- [ ] Hallucinated numerics (e.g., output says "HbA1c 9.0" when retrieval set has 6.8) trigger Mode B rejection.
- [ ] Within tolerance (0.5% on decimals) passes; outside fails.
- [ ] Gateway retries up to 2 times before fail-closing.
- [ ] `pytest tests/intelligence/test_observation_generator.py tests/gateway/test_layer3.py tests/gateway/test_citation_mode_b.py -q` green.
- [ ] Banned-phrase list is exported and importable by task 15's adversarial suite.

## Verification

- `pytest tests/intelligence tests/gateway -q`
- `python -m src.intelligence.observation_generator "vitalog:hba1c"` — prints a single-sentence observation
- Manually inject a bad output via mocking; confirm Layer 3 rejects it.
