# B5 — Mode B citation verifier (parse-and-match)

**Epic:** AI Gateway + Guardrails
**Points:** 5
**Priority:** Critical
**Depends on:** B1, A3
**Architecture refs:** §7.2.1 Mode B; §12 limitations 12, 13 (qualitative + date gaps); PRD v2 Citation Mode B row

## User story

As Mark asking Vitalog questions in natural language,
I want every number the system mentions in prose to be matched against my stored records before I see it,
So that hallucinated values can't slip through a chatty NLQ or observation response just because the prompt isn't tool-use-structured.

## Why this matters

Mode A is too rigid for prose outputs (Observation Generator, NLQ Handler). Mode B is the structurally-weaker but format-friendly equivalent: parse numerics out of the model's prose, match each against the retrieval set, reject if any can't be matched. It's the difference between "robotic but verified" and "natural but verified".

## Acceptance criteria

1. **Given** a prose response like "Your HbA1c on March 12, 2026 was 6.8%, down from 7.1% in January", **When** Mode B runs, **Then** it extracts `6.8` and `7.1`, matches each within ±0.5% to records in the retrieval set, and returns `Valid` if both match.
2. **Given** a prose response containing a numeric the retrieval set does not contain (e.g., "7.0%"), **When** Mode B runs, **Then** the generation is rejected with an `UnmatchedNumericError` listing the offending number.
3. **Given** a prose response with a unit adjacent to a numeric (e.g., "120 mg/dL"), **When** Mode B runs, **Then** the unit must match the matched record's `canonical_unit` OR `original_unit`; a unit mismatch rejects the generation.
4. **Given** integer numerics (e.g., "BP 120/80"), **When** Mode B matches, **Then** exact integer match is required (no tolerance for integers).
5. **Given** decimal numerics, **When** Mode B matches, **Then** the ±0.5% tolerance is applied against `canonical_value` OR `original_value`.
6. **Given** any verification failure, **When** the Gateway retries once with a stricter prompt and that retry also fails, **Then** the caller receives a safe refusal — never partial output.

## Files to create / modify

- `src/gateway/citation_verifier_mode_b.py`
- `src/gateway/numeric_parser.py` — extracts (value, optional_unit, optional_context) tuples from prose
- `src/gateway/errors.py` — add `UnmatchedNumericError`, `UnitMismatchError`
- `tests/gateway/test_mode_b_verifier.py`
- `tests/gateway/test_numeric_parser.py`
- `tests/gateway/fixtures/mode_b/` — prose fixtures with expected matches

## Implementation notes

- The numeric parser must handle: bare decimals (`6.8`), units (`6.8%`, `120 mg/dL`), ranges (`120/80` → two integers), scientific notation (rare; cover anyway), parenthesized values (`HbA1c (6.8%)`).
- Common false-positive numerics to NOT extract: ages ("56-year-old"), dates ("March 12, 2026"), years ("in 2024"), record counts ("9 results"). Heuristic: numbers immediately preceded by month names or "year" words, or immediately followed by "results"/"records"/"patients", are ignored.
- Mode B does NOT verify dates, qualitative claims (e.g., "trending up"), or detect cross-biomarker numeric collisions — these gaps are documented in architecture §12 and mitigated by L3 banned-phrase regex.
- The retrieval set is passed explicitly into `verify(prose, retrieval_set)` — same contract as Mode A.
- Tolerance: `MODE_B_NUMERIC_TOLERANCE = 0.005` (±0.5%) for decimals; exact for integers.
- Logging: every match attempt logged to eval-log with value, matched_record_id (or null), result. Enables auditability of the verifier itself.

## Verification

- `pytest tests/gateway/test_numeric_parser.py -q` — covers parser edge cases (dates, ages, scientific, ranges)
- `pytest tests/gateway/test_mode_b_verifier.py -q` covering all 6 ACs
- Integration with F2 / F3: once those land, run `pytest -m integration tests/intelligence/test_observation_generator.py` and `test_nlq_handler.py` end-to-end with forced mismatches

## INVEST check

- [x] Independent — only B1 + A3 contracts required
- [x] Negotiable — parser heuristics flexible
- [x] Valuable — gates F2 and F3
- [x] Estimable — well-bounded
- [x] Small — 5 pts
- [x] Testable — extensive fixture coverage

## Deferred (explicitly out of this story)

- Date verification in prose (architecture §12 limitation 13; v1)
- Qualitative claim verification (architecture §12 limitation 12; v1)
- Cross-biomarker numeric collision detection (v1)
- ML-based numeric extraction (capstone is regex + heuristics)

## Notes / changelog

_(append after work is done)_
