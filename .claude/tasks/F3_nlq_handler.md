# F3 — NLQ Handler (retrieval-first, Mode B)

**Epic:** Intelligence
**Points:** 5
**Priority:** High
**Depends on:** B1, B3, B5, A3
**Architecture refs:** §5.4.3; PRD v2 Query handler prompt; PRD v2 Scenarios 4, 5

## User story

As Mark asking Vitalog "show me my diabetes markers" or "what was my last HbA1c?",
I want the system to answer from MY stored data only, in natural language, with graceful fallback if I haven't uploaded the relevant test,
So that I can interrogate my own record without the system pulling answers from general medical knowledge.

## Why this matters

The hard constraint "answers ONLY from stored data, never general medical knowledge" is what separates Vitalog from a chatbot. Retrieval-first means the LLM has nowhere to wander: it composes grounded answers from a tight retrieval set or it gracefully says "we don't have that data".

## Acceptance criteria

1. **Given** a query "show me my diabetes markers", **When** NLQ runs, **Then** retrieval-first logic resolves "diabetes markers" → biomarker IDs via the condition→biomarker map, fetches each biomarker's most recent record + trend summary, and the LLM composes a grounded answer that names each marker, its latest value, and its latest collection date.
2. **Given** a query about a biomarker Mark has never uploaded (e.g., "what's my TSH?"), **When** NLQ runs, **Then** retrieval returns empty for that biomarker AND the response is the graceful fallback: "We don't have any TSH results yet. Upload a lab report that includes this test."
3. **Given** the L3 stack, **When** any output numeric is not in the retrieval set, **Then** Mode B rejects the generation and a safe refusal is returned.
4. **Given** a query the system can't interpret (off-topic, gibberish), **When** NLQ runs, **Then** the safe-refusal response is returned ("I can only answer questions about your stored health records.").
5. **Given** the contract, **When** I read `src/intelligence/nlq_handler.py`, **Then** retrieval ALWAYS runs before the LLM is called — there is no path where the LLM is asked to "just answer" without retrieval.
6. **Given** the audit log, **When** an NLQ runs, **Then** event_type `nlq_answered` is logged with the query (PII-redacted), retrieval-set size, prompt version.

## Files to create / modify

- `src/intelligence/nlq_handler.py`
- `src/intelligence/retrieval.py` — query → retrieval-set resolver (parses biomarker names, condition refs, date scopes)
- `prompts/nlq/v1.md`
- `prompts/nlq/v1.frontmatter.yaml`
- `tests/intelligence/test_nlq_handler.py`
- `tests/intelligence/test_retrieval.py`

## Implementation notes

- Retrieval-first means the function is structured: (1) parse query intent, (2) resolve referenced biomarkers/conditions to canonical IDs, (3) fetch records, (4) if empty → graceful fallback, (5) only otherwise → LLM with retrieval set as the only ground truth.
- Query parsing for capstone is a mix of:
  - Direct biomarker mentions (use Tier 1 alias index — same one E1 uses)
  - Condition references (use the condition→biomarker map from A2)
  - Recency cues ("last", "most recent", "since 2024")
  - Catch-all: send to LLM with intent classification (a small inner LLM call)
- The LLM's prompt is locked: "Answer ONLY using the records provided in the retrieval_set. If the retrieval set is empty for a referenced biomarker, say so explicitly. Never reference general medical knowledge."
- Mode B verifier wired into Gateway L3 — every numeric the LLM emits must match a retrieval-set record. Unmatched numerics reject.
- Graceful-fallback strings are templated (not LLM-generated) so they're reliable.
- Capstone scope: single-turn queries only. Multi-turn / contextual follow-ups deferred to v1.

## Verification

- `pytest tests/intelligence/test_nlq_handler.py -q`
- `pytest tests/intelligence/test_retrieval.py -q`
- After C4 lands: adversarial suite checks NLQ for clinical-advice leakage
- Manual: hero scenario queries — "show me my diabetes markers", "what was my last HbA1c?", "what's my TSH?" (fallback)

## INVEST check

- [x] Independent — B1, B3, B5, A3 contracts required
- [x] Negotiable — exact retrieval heuristics flexible
- [x] Valuable — natural-language access to records
- [x] Estimable — well-bounded
- [x] Small — 5 pts
- [x] Testable — fixture-driven

## Deferred (explicitly out of this story)

- Multi-turn / contextual NLQ — v1
- Visit notes / unstructured content (would change to RAG) — v2
- Cross-document reasoning ("what did Dr. Patel say in November?") — v2

## Notes / changelog

### Implementation (2026-05-17)

**Files created:**
- `src/intelligence/nlq_schemas.py` — `NlqOutput(text)` (LLM tool-use), `NlqResponse(text, retrieval_count, prompt_version, is_fallback)` (public return).
- `src/intelligence/retrieval.py` — `resolve_query` (n-gram alias lookup + condition keyword expansion), `canonical_name`. Punctuation stripping on tokens so "HbA1c?" resolves correctly. Condition word-level matching (≥8 chars) so "diabetes" expands T2D without full display name.
- `src/intelligence/nlq_handler.py` — `NlqHandler.answer()` enforcing retrieval-first (AC5). Graceful templated fallback for missing data, safe-refusal for unrecognized queries, two-attempt Mode B retry then safe-refusal. AC6 audit logging with `query_length` (not raw query).
- `prompts/nlq/v1.md` — 512-token `NlqOutput` prompt; no guideline-range citation (Mode B only checks patient values).
- `tests/intelligence/test_nlq_handler.py` — 17 tests (8 handler + 1 partial-retrieval).
- `tests/intelligence/test_retrieval.py` — 8 resolver unit tests.

**Files modified:**
- `prompts/_registry.yaml` — added `nlq / v1` entry.
- `src/reference_data/__init__.py` — added `@lru_cache(maxsize=1)` to `load_biomarker_groups` (PR review fix).

**Key design decisions:**
- Retrieval set: real patient records only — no synthetic guideline records. NLQ must not cite guideline values; Mode B correctly rejects them.
- Query parsing: pure deterministic (no inner LLM call). n-gram alias index + condition keyword expansion covers all capstone demo queries.
- `patient_conditions` parameter removed (was dead code — not passed to `resolve_query`).

**PR review fixes (PR #23, commit 1aad9cd):**
1. Replaced `"query": query` with `"query_length": len(query)` in audit_repo payload (PII).
2. Removed unused `patient_conditions` parameter from `answer()` signature.
3. Added `@lru_cache(maxsize=1)` to `load_biomarker_groups` in `reference_data/__init__.py`.
4. Added `test_answer_partial_retrieval_absent_text_in_prompt` to cover mixed retrieval path.
