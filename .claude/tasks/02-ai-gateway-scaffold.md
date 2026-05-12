# Task 02 — AI Gateway scaffold

## Context

Per architecture §7.1, every LLM call in Vitalog routes through a single chokepoint. The Gateway owns: prompt registry, model routing, schema enforcement, eval logging, layered guardrails. Other services never import `anthropic` directly. Building this first means the rest of the pipeline can be tested with a stubbed Gateway and benefits from logging from day one.

## Dependencies

- Task 00 (repo bootstrap)
- Task 01 (Pydantic schemas — Gateway uses them as response models)

## In scope

`src/gateway/` module:

- `client.py` — wraps Anthropic Python SDK. Single class `AnthropicAdapter` with `complete(messages, tools, model, max_tokens)`. Other providers stubbed but not wired (architecture §11 capstone scope: single-provider per ADR-08).
- `gateway.py` — `Gateway.call(prompt_id: str, vars: dict, response_model: Type[BaseModel]) -> BaseModel`:
  1. Load prompt from registry by `prompt_id` (e.g. `classifier@v1`).
  2. Render template with `vars`.
  3. Apply Layer 1 (input PII regex + injection-pattern detection).
  4. Apply Layer 2 (inject shared safety preamble + few-shot refusals from the prompt's frontmatter).
  5. Call `AnthropicAdapter.complete` with tool-use schema derived from `response_model.model_json_schema()`.
  6. Parse tool-use response → `response_model` instance.
  7. Apply Layer 3 stub (real validators wired by tasks 12/13).
  8. Log to JSONL via `eval_logger`.
  9. Return parsed model.
- `prompt_registry.py` — filesystem-backed. Reads `prompts/<name>/<version>.md` with frontmatter:
  ```
  ---
  prompt_id: classifier
  version: 1
  model: claude-sonnet-4-6
  temperature: 0.1
  response_model: src.schemas.documents.ClassificationResult
  safety_preamble: standard_no_clinical_advice
  ---
  <prompt template using {{var}} placeholders>
  ```
- `safety_preambles.py` — one constant per preamble id; `standard_no_clinical_advice` is the only one needed for capstone.
- `guardrails/layer1.py` — PII regex (SSN, email, phone) — redacts for logging only, not for the call itself (since synthetic data has no real PII in capstone). Injection-pattern detection: refuse if prompt contains `ignore previous instructions`, `system prompt`, etc.
- `guardrails/layer2.py` — preamble injector + few-shot refusal injector.
- `guardrails/layer3.py` — stub interface `Validator.validate(output) -> ValidationResult`; concrete validators added in tasks 12/13.
- `eval_logger.py` — `EvalLogger.log(prompt_id, version, input_hash, output, latency_ms, cost_usd, gateway_metadata)`. Writes JSONL to `eval_corpus/runs/<date>.jsonl`.

Registry seeded with one placeholder prompt: `prompts/echo/v1.md` for testing the Gateway end-to-end without real prompts.

## Out of scope (deferred)

- Real multi-provider routing (architecture §11 — stub adapter only).
- LLM-as-judge (Layer 4, v1).
- Cost tracking dashboard (v1).
- Prompt caching (deferred — Anthropic prompt caching can be added v1).

## Files to create

- `src/gateway/__init__.py` (re-export `Gateway`)
- `src/gateway/client.py`
- `src/gateway/gateway.py`
- `src/gateway/prompt_registry.py`
- `src/gateway/safety_preambles.py`
- `src/gateway/eval_logger.py`
- `src/gateway/guardrails/__init__.py`
- `src/gateway/guardrails/layer1.py`
- `src/gateway/guardrails/layer2.py`
- `src/gateway/guardrails/layer3.py`
- `prompts/echo/v1.md` (placeholder test prompt)
- `tests/gateway/test_gateway.py` (with mocked Anthropic client)
- `tests/gateway/test_prompt_registry.py`
- `tests/gateway/test_guardrails.py`

## Architecture references

- `docs/Vitalog_architecture.md` §7.1 — AI Gateway in detail
- `docs/Vitalog_architecture.md` §7.2 — Layered guardrails
- `docs/Vitalog_architecture.md` §7.2.1 — citation verification (Mode A binding shape)
- `docs/Vitalog_PRD_v2.md` §Functional Requirements "Safety — AI Gateway", "Safety — Guardrails L1/L2/L3"

## Step-by-step

1. Write `prompt_registry.py` first — pure I/O + parsing, easy to test.
2. Write `AnthropicAdapter` with `messages.create` tool-use call.
3. Write `Gateway.call` orchestration; mock the adapter in tests.
4. Layer 1 + Layer 2 implementations.
5. Layer 3 stub returns `ValidationResult(passed=True)` until tasks 12/13 plug in concrete validators.
6. Eval logger writes JSONL; rotate by date.
7. End-to-end test using `prompts/echo/v1.md` and a mocked adapter returning a static tool-use response.

## Acceptance criteria

- [ ] `pytest tests/gateway -q` — all green with mocked adapter.
- [ ] Calling `Gateway.call("echo@v1", {"text": "hi"}, EchoResponse)` returns a parsed `EchoResponse`.
- [ ] One JSONL line written per call.
- [ ] Injecting `ignore previous instructions` in `vars` triggers Layer 1 rejection (not a real LLM call).
- [ ] No code outside `src/gateway/` imports `anthropic`.
- [ ] `mypy src/gateway --strict` clean.

## Verification

- `pytest tests/gateway -q`
- `grep -r "import anthropic" src/ | grep -v "src/gateway/"` — must be empty.
- Manual: tail `eval_corpus/runs/$(date +%Y-%m-%d).jsonl` after running tests.
