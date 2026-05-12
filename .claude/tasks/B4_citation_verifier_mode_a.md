# B4 — Mode A citation verifier (structured citation)

**Epic:** AI Gateway + Guardrails
**Points:** 5
**Priority:** Critical
**Depends on:** B1, A3
**Architecture refs:** §7.2.1 Mode A; §12 limitation 11 (arithmetic not verified); PRD v2 Citation Mode A row

## User story

As Mark relying on the appointment summary,
I want every numeric biomarker value the Summary Generator produces to be deterministically traced back to a stored record I own,
So that no hallucinated value can reach my cardiologist via Vitalog.

## Why this matters

Mode A is the load-bearing safety guarantee for the Summary Generator. A hallucinated HbA1c value in a clinician-facing artifact is the single worst failure mode this product can produce. Mode A makes that failure mode mechanically prevented, not just prompt-prevented.

## Acceptance criteria

1. **Given** a generated summary where every numeric value is wrapped in a `Citation{value, unit, collection_date, source_record_id}`, **When** every cited `source_record_id` resolves to a record in the retrieval set with matching `patient_id`, matching `canonical_unit`, matching `collection_date`, and `canonical_value` within ±0.5%, **Then** the verifier returns `Valid`.
2. **Given** a generated summary with a citation pointing to a `source_record_id` not in the retrieval set, **When** Mode A runs, **Then** the entire generation is atomically rejected and a security event is logged.
3. **Given** a generated summary with a citation whose `canonical_value` differs by 0.6% from the stored record, **When** Mode A runs, **Then** the generation is rejected.
4. **Given** a generated summary with a citation whose `patient_id` differs from the generation context, **When** Mode A runs, **Then** the generation is rejected and logged as a security event (ownership-leak attempt).
5. **Given** a Mode A failure, **When** the Gateway retries once with a stricter prompt and that retry also fails verification, **Then** the caller receives a safe refusal — never partial output.
6. **Given** a derived statement like "HbA1c improved by 0.4% over six months", **When** the prompt has correctly cited both endpoint records, **Then** Mode A passes; the verifier does NOT independently verify the arithmetic (documented limitation §12).

## Files to create / modify

- `src/gateway/citation_verifier_mode_a.py`
- `src/gateway/citation_schemas.py` — `Citation` Pydantic model
- `src/gateway/errors.py` — add `ModeAVerificationError`, `OwnershipLeakError`
- `tests/gateway/test_mode_a_verifier.py`
- `tests/gateway/fixtures/mode_a/` — pass/fail/security-event fixtures

## Implementation notes

- Verifier is pure-deterministic. Zero LLM calls in this path.
- Tolerance constant `MODE_A_NUMERIC_TOLERANCE = 0.005` (±0.5%). Stored alongside the verifier, named constant per project Gotchas.
- Reuse `BiomarkerRepository.get(record_id)` from A3 — do NOT add a Mode-A-only lookup path.
- Atomic rejection means: throw a typed `ModeAVerificationError`, no partial summary ever returned. Caller (Summary Generator) catches and returns the safe refusal.
- Security event logging: separate `verification.security` logger, written at error level with the full citation that failed, the generation context patient_id, and the offending source_record_id. PII redacted per Layer 1.
- The retrieval set must be passed explicitly into `verify(summary, retrieval_set)` — the verifier does not pull from Supabase on its own. Keeps the surface tight.

## Verification

- `pytest tests/gateway/test_mode_a_verifier.py -q` covering all 6 ACs
- `pytest tests/gateway/test_mode_a_verifier.py::test_ownership_leak` — must log security event
- Integration with F5: once F5 lands, run `pytest -m integration tests/intelligence/test_summary_generator.py` end-to-end and confirm any forced citation mismatch produces refusal

## INVEST check

- [x] Independent — only B1 and A3 contracts required
- [x] Negotiable — internal implementation flexible
- [x] Valuable — single biggest safety guarantee in the product
- [x] Estimable — 5 pts; deterministic code with clear contract
- [x] Small — ≤8 pts
- [x] Testable — fixture-driven, no network

## Deferred (explicitly out of this story)

- Arithmetic verification of derived values (architecture §12 limitation 11; v1)
- LLM-as-judge fallback for subtle inference (architecture §12 limitation 14; v1)
- Cross-biomarker numeric collision detection (v1)

## Notes / changelog

_(append after work is done)_
