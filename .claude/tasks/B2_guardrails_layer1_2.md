# B2 — Layer 1 + Layer 2 guardrails

**Epic:** AI Gateway + Guardrails
**Points:** 3
**Priority:** High
**Depends on:** B1
**Architecture refs:** §7.1, §7.2 (L1, L2 rows)

## User story

As Mark using Vitalog,
I want every LLM call to redact my PHI from logs and to be wrapped in a shared safety preamble with few-shot refusal examples,
So that observability never leaks my data and most clinical-advice attempts are deflected before they reach me.

## Why this matters

Layer 1 keeps PHI out of eval logs (which are written to disk and may be shared with collaborators). Layer 2 is the cheapest, broadest defense against clinical advice — the few-shot refusals teach the model the expected refusal shape so it doesn't have to be invented from scratch under adversarial pressure.

## Acceptance criteria

1. **Given** an input containing a recognized PHI token (name, DOB, MRN, phone, email, address pattern), **When** Layer 1 processes the input for logging, **Then** the token is replaced with a stable redaction tag (e.g., `[PHI:NAME]`) before being written to the eval log or audit log.
2. **Given** a prompt-injection pattern (e.g., "ignore previous instructions", "you are now", "system:", "</system>"), **When** Layer 1 scans the input, **Then** a `PromptInjectionDetected` event is logged and the call proceeds with the offending text marked but not deleted (the model still sees the sanitized version with a warning preamble).
3. **Given** any prompt assembled by the Gateway, **When** the model is called, **Then** the assembled prompt contains the shared safety preamble verbatim as its first system-content block.
4. **Given** the registered prompt `summary_cardiology@v1`, **When** it is assembled, **Then** at least 3 few-shot refusal examples are injected (e.g., "Q: Should I take more metformin? A: I can't give medical advice; please ask your doctor.").
5. **Given** the output of any structured-output call, **When** the model returns a tool-use response, **Then** the schema is enforced by the adapter; non-conforming outputs trigger one retry with a tightened prompt.
6. **Given** the L1 + L2 contract, **When** I read the unit tests, **Then** there is a test covering each of: PHI redaction, injection detection, preamble presence, few-shot inclusion, schema enforcement retry.

## Files to create / modify

- `src/gateway/guardrails/layer1.py` — PII/PHI redactor + injection detector
- `src/gateway/guardrails/layer2.py` — preamble + few-shot loader + schema enforcement helpers
- `src/gateway/guardrails/__init__.py`
- `prompts/_shared/safety_preamble.md` — the canonical preamble (versioned)
- `prompts/_shared/few_shot_refusals/`*`.md` — at least 3 refusal examples
- `src/gateway/gateway.py` — wire L1 + L2 into `Gateway.call()`
- `tests/gateway/test_layer1_redaction.py`
- `tests/gateway/test_layer1_injection.py`
- `tests/gateway/test_layer2_preamble.py`

## Implementation notes

- Capstone PHI redactor is regex-based, NOT the full Safe Harbor list (that's v1.5). Cover: names from a small allow-list, DOB patterns (`\d{4}-\d{2}-\d{2}`, `\d{1,2}/\d{1,2}/\d{2,4}`), phone, email, MRN-like (`MRN[\s:]*\d+`). Document this explicitly as a capstone limitation.
- Redaction is for logs only. The model still sees the original PHI — the patient is the data owner, redaction-for-logs and redaction-for-model are different concerns (the latter is v1.5).
- Injection detection is heuristic; false positives are acceptable as long as they're logged, not blocked. The Gateway should never silently drop content (per §7.5 "fail loud at boundaries").
- The safety preamble is the SAME string across all prompts. Versioning it bumps every prompt's effective behavior, which is the right level of churn.
- Few-shot refusals are loaded from disk so they can be edited without code changes; the prompt registry stamps the version into eval logs.
- Schema enforcement = Claude tool-use forced choice. If the model emits a non-tool response, retry once with `"You must call the {tool_name} tool"` appended.

## Verification

- `pytest tests/gateway/test_layer1_redaction.py -q`
- `pytest tests/gateway/test_layer1_injection.py -q`
- `pytest tests/gateway/test_layer2_preamble.py -q`
- Manual: run a Gateway call with PHI in inputs, confirm the eval-log row contains redaction tags

## INVEST check

- [x] Independent — only B1 required
- [x] Negotiable — exact regex set flexible; coverage of categories fixed
- [x] Valuable — first line of safety defense
- [x] Estimable — well-bounded
- [x] Small — 3 pts
- [x] Testable — every AC has a corresponding test

## Deferred (explicitly out of this story)

- Full Safe Harbor PHI redaction pipeline (v1.5)
- ML-based injection detection (capstone is regex only)
- Per-prompt preamble overrides — single shared preamble is intentional

## Notes / changelog

### Implementation — 2026-05-14

**Files created:**
- `src/gateway/guardrails/__init__.py` — re-exports `Layer2`, `detect_injection`, `redact_for_log`
- `src/gateway/guardrails/layer1.py` — PHI regex redactor (email, phone, DOB, MRN) + heuristic injection detector (6 patterns, warns and proceeds, never blocks)
- `src/gateway/guardrails/layer2.py` — `Layer2` class: loads `safety_preamble.md` + `few_shot_refusals/*.md` once at init; `augment_system()` prepends preamble + refusals + optional injection warning
- `prompts/_shared/safety_preamble.md` — Vitalog "not a medical device" preamble
- `prompts/_shared/few_shot_refusals/medical_advice.md` — refusal example
- `prompts/_shared/few_shot_refusals/diagnosis.md` — refusal example
- `prompts/_shared/few_shot_refusals/medication_adjustment.md` — refusal example
- `tests/gateway/test_layer1_redaction.py` — 10 tests covering all PHI patterns + eval log integration
- `tests/gateway/test_layer1_injection.py` — 11 tests covering all injection patterns + gateway integration
- `tests/gateway/test_layer2_preamble.py` — 10 tests covering preamble, refusals, schema enforcement retry

**Files modified:**
- `src/gateway/gateway.py` — wired L1 + L2: original inputs used for template rendering (not redacted), `log_inputs` (PHI-redacted) go to eval log; new seam methods `_check_injection`, `_assemble_system`; `_apply_input_filters` now calls `layer1.redact_for_log`
- `src/gateway/anthropic_adapter.py` — added schema enforcement retry: when model returns no `tool_use` block, retries once with `"You must call the {tool_name} tool."` appended to user content

**Key design decisions:**
- PHI redaction is log-only per task notes (model sees original inputs); enforced by using `inputs` for `format_map()` and `log_inputs` for eval writes
- Injection detection never blocks: logs a warning and returns a preamble string prepended to system prompt (§7.5 "fail loud at boundaries")
- `Layer2` loaded once in `Gateway.__init__`, not per-call
- Schema enforcement retry is inside the adapter loop; uses one retry slot from `max_retries`; no sleep between attempts

**Test results:** 38/38 pass (`pytest tests/gateway/ -q`). `make lint` and `make typecheck` clean.
