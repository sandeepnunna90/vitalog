# B3 — Layer 3 deterministic validators (banned-phrase + schema)

**Epic:** AI Gateway + Guardrails
**Points:** 3
**Priority:** High
**Depends on:** B1
**Architecture refs:** §7.2 (Layer 3 regex + schema rows)

## User story

As Mark relying on Vitalog's safety story,
I want every LLM output to be screened against a banned-phrase list AND a strict Pydantic schema before it reaches me,
So that explicit clinical-advice language ("you should", "I recommend") never escapes the system and malformed outputs never silently corrupt downstream code.

## Why this matters

L2 prompt-level constraints are insufficient under prompt drift and adversarial framing (architecture §12 limitation 14 acknowledges this). L3 regex is the cheap, deterministic backstop that catches the obvious failure modes regardless of how the model behaves on a given day. Pydantic schema validation is the corresponding guarantee for structure.

## Acceptance criteria

1. **Given** the banned-phrase regex list, **When** an LLM output contains any banned phrase ("you should", "I recommend", "you need to", "consider taking", "diagnosed with", "stop taking", etc.), **Then** Layer 3 rejects the output and returns a typed `BannedPhraseViolation` error.
2. **Given** a banned-phrase violation, **When** the Gateway sees it, **Then** it retries once with a stricter prompt that explicitly references the offending phrase; if the retry also fails, the caller receives a safe refusal.
3. **Given** an LLM output that does not match the declared Pydantic `output_schema`, **When** Layer 3 validates it, **Then** a `SchemaValidationError` is raised with a diff of the offending fields.
4. **Given** a schema validation failure, **When** the Gateway retries once, **Then** the retry is allowed; on second failure, the caller receives a safe refusal — never partial output.
5. **Given** the banned-phrase list, **When** I inspect it, **Then** it is loaded from `prompts/_shared/banned_phrases.txt` (one phrase per line, case-insensitive), versioned with the prompt registry.
6. **Given** the L3 contract, **When** any prompt is registered, **Then** it MUST declare an `output_schema` (Pydantic model name) — the registry rejects prompts without one.

## Files to create / modify

- `src/gateway/guardrails/layer3_deterministic.py` — banned-phrase scanner + schema validator
- `prompts/_shared/banned_phrases.txt` — initial list of ~25 phrases
- `src/gateway/errors.py` — add `BannedPhraseViolation`, `SchemaValidationError`
- `src/gateway/gateway.py` — wire L3 into `Gateway.call()` after model invocation
- `tests/gateway/test_layer3_banned_phrases.py`
- `tests/gateway/test_layer3_schema_validation.py`
- `tests/gateway/test_layer3_retry_then_refuse.py`

## Implementation notes

- Banned phrases are case-insensitive whole-word matches (use `\b` boundaries) to reduce false positives like "consider" (legitimate) vs "consider taking" (banned).
- The banned-phrase list is intentionally aggressive — Mode A + Mode B handle numerics, banned-phrase handles qualitative claims. Acceptable false-positive rate at capstone is ~5% (would be tuned in v1).
- Schema validation reuses Pydantic — no separate validator framework. The Gateway already enforces tool-use schemas at the model layer; L3 schema validation is the belt to that suspenders, catching cases where the adapter let something through.
- "Stricter prompt" on retry = preamble + explicit list of phrases the prior attempt produced + "DO NOT use any of these phrases or this output will be rejected."
- The full L3 stack order: schema → banned-phrase → citation verifier (B4 or B5 depending on caller). If any layer fails, downstream layers are skipped — the output is rejected as a whole.

## Verification

- `pytest tests/gateway/test_layer3_banned_phrases.py -q` covering each phrase category
- `pytest tests/gateway/test_layer3_schema_validation.py -q`
- `pytest tests/gateway/test_layer3_retry_then_refuse.py -q` — proves no partial output on double failure
- Manual: feed a known-bad output through `Gateway._apply_output_validators`, observe the rejection

## INVEST check

- [x] Independent — only B1 required
- [x] Negotiable — exact phrase list flexible; categories fixed
- [x] Valuable — explicit safety guarantee
- [x] Estimable — well-bounded
- [x] Small — 3 pts
- [x] Testable — phrase-by-phrase unit tests

## Deferred (explicitly out of this story)

- LLM-as-judge layer (architecture §12 limitation 14; v1)
- Citation verification (B4 Mode A, B5 Mode B)
- Adversarial regression runner (C4)
- Phrase-list versioning UI (capstone uses git)

## Notes / changelog

_(append after work is done)_
