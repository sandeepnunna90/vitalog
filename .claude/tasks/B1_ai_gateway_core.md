# B1 — AI Gateway core

**Epic:** AI Gateway + Guardrails
**Points:** 5
**Priority:** Critical
**Depends on:** A1
**Architecture refs:** §5.5, §7.1, P3 (single chokepoint), ADR-05, ADR-08

## User story

As the founder building Vitalog,
I want a single `Gateway.call(prompt_id, version, inputs, output_schema)` chokepoint that every LLM-touching service must go through,
So that prompt versioning, model routing, guardrails, and eval logging happen uniformly and no service can bypass them (P3).

## Why this matters

P3 is the single most important architectural rule. If even one service calls Anthropic directly, the guardrail story collapses. Building the Gateway before any other LLM-touching code makes "you must use the Gateway" enforceable by lint, not by hope.

## Acceptance criteria

1. **Given** a registered prompt `extract@v1`, **When** I call `Gateway.call("extract", "v1", inputs, OutputModel)`, **Then** the prompt is assembled from the registry, sent to Anthropic with `OutputModel` enforced via tool-use schema, and a validated `OutputModel` instance is returned.
2. **Given** an unregistered `prompt_id` or `version`, **When** I call `Gateway.call(...)`, **Then** a `PromptNotFoundError` is raised before any network call.
3. **Given** any call to the Gateway, **When** it completes (success OR failure), **Then** an eval-log row is written containing `prompt_id`, `version`, `model`, `inputs` (PII-redacted), `outputs`, `latency_ms`, `token_counts`, `success`.
4. **Given** an audit-log requirement, **When** any Gateway call runs, **Then** an audit-log entry is recorded via `AuditLogRepository` with event_type `"llm_call"`.
5. **Given** a transient Anthropic API error (e.g., 429 / 5xx), **When** the Gateway invokes the model, **Then** it retries with exponential backoff (up to 3 attempts) and only then fails soft to the caller.
6. **Given** the project standard, **When** I `grep -r "anthropic.Anthropic(" src/` outside `src/gateway/`, **Then** zero matches are found (enforced by a lint rule or a unit test that walks the AST).

## Files to create / modify

- `src/gateway/__init__.py` — public `Gateway` class
- `src/gateway/gateway.py` — `Gateway.call(prompt_id, version, inputs, output_schema)`
- `src/gateway/prompt_registry.py` — loads from `prompts/<concern>/<version>.md`, validates frontmatter
- `src/gateway/anthropic_adapter.py` — wraps the Anthropic SDK with tool-use schema enforcement
- `src/gateway/model_router.py` — capstone: single-provider routing table (`structurer → claude-sonnet-4-6`, `vision_fallback → claude-sonnet-4-6` with vision input)
- `src/gateway/eval_logger.py` — writes to `eval_corpus/runs/<date>/<run_id>.jsonl`
- `src/gateway/errors.py` — typed exception hierarchy
- `prompts/_registry.yaml` — list of registered (prompt_id, version) pairs
- `tests/gateway/test_gateway_call.py`
- `tests/gateway/test_no_direct_anthropic_imports.py` — AST walk, fails CI if any non-gateway file imports `anthropic`

## Implementation notes

- The Gateway exposes ONE entry point. No public `_call_anthropic_directly()`, no escape hatch.
- Prompts are markdown files with YAML frontmatter (model preference, tool-use schema name, max_tokens). The body is the rendered system + user message template.
- Model selection: capstone is single-provider (ADR-08) but the model_router accepts a `task` enum so v1's multi-provider work is additive, not invasive.
- Tool-use schema is the enforcement mechanism for structured outputs — the `output_schema` parameter is converted to a Claude tool definition and the model is forced to call it.
- The Gateway does NOT yet apply L1/L2/L3 guardrails — those land in B2/B3/B4/B5 and plug into the same chokepoint. Make the seams explicit (`_apply_input_filters`, `_apply_output_validators`) so plugging guardrails is a one-file change.
- Eval logger writes JSONL, not Postgres — keeps the eval pipeline runnable offline.
- The Anthropic adapter must accept image inputs (for D5 vision fallback) — design the interface accordingly even though only structurer/classifier ship in B1.

## Verification

- `pytest tests/gateway/ -q` — all unit tests green (no network)
- `pytest tests/gateway/test_no_direct_anthropic_imports.py` — AST walker passes
- Manual sanity: register a `hello@v1` prompt, call the Gateway, observe the eval-log row and the audit-log row

## INVEST check

- [x] Independent — only A1 required
- [x] Negotiable — internal layering flexible
- [x] Valuable — gates every LLM-touching story
- [x] Estimable — well-bounded surface
- [x] Small — 5 pts
- [x] Testable — chokepoint enforceable by AST walker

## Deferred (explicitly out of this story)

- Layer 1 / Layer 2 / Layer 3 guardrails (B2, B3, B4, B5)
- Multi-provider adapters with real wiring (v1)
- Streaming responses (not needed for capstone)
- Prompt caching (Anthropic feature; deferred to v1)

## Notes / changelog

### Implementation — 2026-05-14

**Files created:**
- `src/gateway/errors.py` — `GatewayError`, `PromptNotFoundError`, `OutputValidationError`, `ModelError`
- `src/gateway/model_router.py` — `default_model()` returns `"claude-sonnet-4-6"`; v1 adds Task enum + route table additively
- `src/gateway/prompt_registry.py` — `PromptRegistry` eagerly loads `prompts/_registry.yaml` + all referenced `.md` files at construction; `PromptTemplate` dataclass holds resolved fields; raises `PromptNotFoundError` on unknown prompt
- `src/gateway/anthropic_adapter.py` — sole file in `src/` permitted to `import anthropic`; forced tool-use via `tool_choice={"type":"tool","name":...}`; retries on 429/5xx with sleeps 0s/1s/2s; raises `ModelError` after exhaustion; accepts `str | list[dict]` user_content for image inputs
- `src/gateway/eval_logger.py` — `EvalLogger.log()` writes one JSONL per call to `eval_corpus/runs/<YYYY-MM-DD>/<run_id>.jsonl`; `make_entry()` factory populates all fields
- `src/gateway/gateway.py` — `Gateway.call()` chokepoint; `_apply_input_filters` and `_apply_output_validators` are overrideable seams for B2–B5 guardrails (pass-through in B1); audit log optional (None-safe); eval log failure never propagates to caller
- `src/gateway/__init__.py` — re-exports `Gateway` + all error classes
- `prompts/_registry.yaml` — registry index
- `prompts/hello/v1.md` — sample prompt for unit tests
- `tests/gateway/test_gateway_call.py` — 7 unit tests covering all 5 ACs; all mocked, zero network
- `tests/gateway/test_no_direct_anthropic_imports.py` — AST walker enforcing P3

**Modified:**
- `pyproject.toml` — added `pyyaml>=6.0`
- `mypy.ini` — added `[mypy-yaml] ignore_missing_imports = True`

**Design decisions:**
- Prompt frontmatter uses `system_template` + `user_template` fields (not a `---` body separator) to avoid markdown HR ambiguity
- `audit_repo` is optional (`None`) so unit tests run without a live Supabase connection
- `block.input` typing: `type: ignore[call-overload]` on `messages.create()` because the `str | list[dict]` union for `content` is valid at runtime but mypy can't verify it through the SDK's overloaded signatures
- Retry sleep schedule stored in a dict (`{0: 0.0, 1: 1.0, 2: 2.0}`) so tests can patch `time.sleep` cleanly

**Verification results:**
- `pytest tests/gateway/ -v` → 8/8 passed
- `make lint` → clean
- `make typecheck` → clean (24 source files, 0 errors)
- `grep -r 'anthropic' src/ --include='*.py' | grep -v 'src/gateway/'` → zero lines (AC 6)
