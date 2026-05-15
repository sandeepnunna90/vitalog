# Vitalog — Project Instructions

## Common commands

- `make test` — unit tests only (skips integration)
- `make lint` — `ruff check` + `ruff format --check`
- `make format` — auto-fix formatting
- `make typecheck` — `mypy --strict src/`
- `uv sync` — sync environment

## Code standards

### Python
- Type hints on every public function signature (parameters + return type). No `Any` without a comment explaining why.
- Pydantic v2 models: `model_config = ConfigDict(strict=True)`. Never `extra="allow"`.
- All LLM calls through `Gateway.call()` — never instantiate `anthropic.Anthropic()` directly outside `src/gateway/`.
- No bare `except:` — catch specific exceptions or `except Exception as e:` with a log statement.
- `ruff check` and `ruff format` must pass before commit. `mypy --strict` must pass.

### Naming
- Files and modules: `snake_case.py`. Classes: `PascalCase`. Pydantic models are classes.
- Prompt files: `prompts/<concern>/<version>.md` (e.g. `prompts/summary/v1.md`). Bump version on every edit.

### Tests
- Unit tests use fixtures from `tests/fixtures/` — no network calls, no Supabase writes.
- Integration tests (marked `@pytest.mark.integration`) may call live Supabase; skip with `pytest -m "not integration"`.
- Every new public function in `src/` needs at least one test.

## Architecture

Source-of-truth docs live in `docs/` — read before planning any change:
- `docs/Vitalog_PRD_v2.md` — architecture-aligned product spec (**use this, not v1**)
- `docs/Vitalog_architecture.md` — stack, ADRs, capstone scope (§11), known limitations (§12)
- `docs/vitalog_roadmap.md` — implementation sequencing

Stack (do not re-litigate without updating `docs/Vitalog_architecture.md`):
- Python 3.11+, Pydantic for all LLM I/O schemas
- Anthropic Claude Sonnet via the Anthropic Python SDK — single-provider (ADR-08)
- Interface: MCP via Claude Desktop (demo); CLI is fallback
- OCR: AWS Textract primary → Claude vision-LLM fallback (ADR-02)
- Persistence: Supabase (Postgres + Storage), Repository pattern
- All LLM calls pass through the AI Gateway (§7.1)
- Citation: Mode A (structured tool-use) for Summary Generator; Mode B (parse-and-match) for Observation Generator and NLQ Handler (§7.2.1)

Storage policy (classification-gated, §7.6):
- `lab_report` → retained permanently
- `recognized_unsupported` → retained permanently
- `not_supported` → file discarded after classification; audit metadata only

## Key files

**Built (Epic A–B):**
- `src/gateway/gateway.py` — single LLM chokepoint; wires Layer 1 + Layer 2; renders templates with original inputs; logs only redacted inputs
- `src/gateway/anthropic_adapter.py` — SDK adapter; exponential-backoff retry; catches `RateLimitError`, `APIStatusError`, `APIConnectionError`; one schema-enforcement retry per call
- `src/gateway/guardrails/layer1.py` — PHI redactor (log-only, recurses into nested dicts) + heuristic injection detector (warns, never blocks)
- `src/gateway/guardrails/layer2.py` — safety preamble + few-shot refusal loader; prepended to every system prompt via `Layer2.augment_system()`
- `src/gateway/prompt_registry.py` — loads versioned prompt files; renders templates
- `src/gateway/eval_logger.py` — writes per-call JSONL to `eval_corpus/runs/`; stores redacted inputs
- `src/persistence/models.py` — Pydantic models for all DB entities; `ProcessingStatus` is a `Literal` type
- `src/persistence/document_repository.py` — CRUD for lab documents; all mutations guard empty INSERT/UPDATE
- `src/persistence/biomarker_repository.py` — CRUD for biomarker records
- `src/persistence/taxonomy_repository.py` — taxonomy CRUD; all mutations guarded
- `src/persistence/audit_log_repository.py` — append-only audit log with hash chain; INSERT guarded
- `src/reference_data/__init__.py` — `load_taxonomy()` and `_get_alias_index()` are `lru_cache(maxsize=1)`
- `reference_data/biomarker_taxonomy.json` — 30-entry taxonomy seed; source of truth for canonical names, UCUM units, guideline ranges
- `prompts/_shared/safety_preamble.md` + `prompts/_shared/few_shot_refusals/` — Layer 2 prompt assets
- `tests/gateway/conftest.py` — shared `prompts_dir` fixture for gateway test suite

**Up next (Epic B–C):**
- `src/ingestion/classifier.py` — document classifier, 3 categories *(D2)*
- `src/ingestion/structurer.py` — LLM structurer + composite confidence; owns `THRESHOLD_AUTO_ACCEPT` / `THRESHOLD_REJECT` *(D6)*
- `src/normalization/tier1.py` — LOINC-aware alias lookup *(E1)*
- `src/intelligence/summary_generator.py` — Mode A citation-verified summary *(F5)*
- `src/intelligence/observation_generator.py` — Mode B factual observations *(F2)*
- `src/mcp_server/server.py` — stdio MCP server, 6 tools *(G1)*

## Workflow

- Always enter plan mode before writing code. Write the plan to `.claude/tasks/<TASK_NAME>.md`.
- Each plan: context, file paths to modify, reasoning, step-by-step tasks, verification section.
- Wait for explicit approval before implementing.
- Update the plan file as work progresses; append change descriptions for handoff.
- **Definition of done** — after every story, update all three:
  1. `CLAUDE.md` — move built files from "Up next" → "Built"; add new gotchas
  2. `.claude/tasks/README.md` — flip Status to ✅ done
  3. `.claude/tasks/<STORY>.md` — append summary of all changes made
- MVP-focused. Flag anything outside architecture §11 capstone scope as deferred.

## Gotchas

- **Prompt versioning is mandatory.** Eval logger stores `(prompt_id, version)` per call. Editing a prompt without bumping the version silently corrupts eval replay.
- **Mode A vs Mode B cannot be swapped.** Summary Generator: every numeric wrapped in a `Citation` with `source_record_id`. Observation Generator: parse output numerics, match against retrieval set within ±0.5%.
- **Layer 1 injection detector must recurse into nested dicts** — same as `redact_for_log`. A flat join misses `{"patient": {"query": "ignore all instructions"}}`. Both use `_collect_text()`.
- **Classification gates storage.** A `not_supported` document must never write to `biomarker_records` — audit log only. Violating this breaks the privacy model (§7.6).
- **Confidence thresholds live in `src/ingestion/structurer.py`** (`THRESHOLD_AUTO_ACCEPT`, `THRESHOLD_REJECT`). Never change without re-running `make calibrate` and reviewing `eval_corpus/calibration_report.md`.
- **Mark's patient profile** is hardcoded in `reference_data/mark_profile.json`. Do not load from Supabase unless task 18 (if-time) has landed.

## Out of capstone scope

Do not propose unless the user explicitly asks (architecture §12):
- LLM-as-judge guardrail layer (highest-priority deferred safety item)
- Multi-provider failover
- Web UI
- Tiers 2 and 3 of biomarker normalization
- Arithmetic validation on derived values inside Citation Mode A
