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

### Implementation (2026-05-17)

**Files created:**
- `src/gateway/numeric_parser.py` — `ExtractedNumeric` frozen dataclass; `parse()` two-pass extractor (BP ranges → general numerics); `_is_valid_unit()` gate rejects English verbs captured as unit tokens; false-positive filters for years, month-preceded dates, ages, and count words
- `src/gateway/citation_verifier_mode_b.py` — `verify(prose, retrieval_set)` module-level function; `MODE_B_NUMERIC_TOLERANCE = 0.005`; `_eval_log = logging.getLogger("verification.eval")`; decimal ±0.5% tolerance, integer exact match; unit checked against `canonical_unit` OR `original_unit`; value matched against `canonical_value` OR `float(original_value)`
- `tests/gateway/test_numeric_parser.py` — 13 unit tests (parser happy paths + 5 false-positive filters)
- `tests/gateway/test_mode_b_verifier.py` — 14 unit tests covering all 6 ACs (AC6 caller-deferred)

**Files modified:**
- `src/gateway/errors.py` — added `ModeBVerificationError`, `UnmatchedNumericError`, `UnitMismatchError`
- `src/gateway/__init__.py` — re-exports all new symbols; `__all__` alphabetically sorted

**Key design decisions:**
- Retrieval set is caller-supplied (`dict[uuid.UUID, BiomarkerRecordRow]`) — verifier does zero I/O
- `_is_valid_unit()` distinguishes real clinical units (contain `%`, `/`, digit, or uppercase) from English words — fixes false `UnitMismatchError` on prose like "6.8 has improved"
- Count words (`results`, `records`, etc.) captured as unit token → skip entire numeric; English verbs captured → keep numeric, drop unit
- `stored == 0.0` edge case handled explicitly (exact match required) to avoid divide-by-zero
- AC6 retry-then-refuse logic deferred to F2/F3 callers (same pattern as B4/AC5)

**PR review fixes (3 commits):**
- Two-word unit regex simplified to single-token only; `_is_valid_unit()` gate added
- `"UnitMismatchError"` / `"UnmatchedNumericError"` swapped in `__all__` to restore alphabetical order
- `verify()` docstring annotated with AC6 caller-defer note
- Dead `first_word in _COUNT_WORDS` branch removed from `_should_skip` (count words always consumed into unit token, handled in `parse()`)
- Added `test_zero_stored_exact_match_passes` / `test_zero_stored_nonzero_cited_raises` for `_within_tol` zero-guard
- Tightened `test_bp_range_with_year_not_extracted` to assert exact extracted values
