# Vitalog — Project Instructions

## Project

Vitalog is an MCP-first health intelligence tool for chronic-condition patients (primary persona: Mark — T2D, HTN, thyroid). It ingests lab reports, normalizes biomarkers against a LOINC/UCUM-aware taxonomy, persists structured records, and surfaces summaries, observations, and natural-language queries through an MCP server consumed by Claude Desktop.

## Source-of-truth documents

Read these before planning any change:

All source-of-truth docs live in [docs/](docs/):

- [docs/Vitalog_PRD_v2.md](docs/Vitalog_PRD_v2.md) — architecture-aligned product spec. **Use this, not v1.**
- [docs/Vitalog_architecture.md](docs/Vitalog_architecture.md) — authoritative for stack, ADRs, capstone scope (§11), and known limitations (§12).
- [docs/vitalog_roadmap.md](docs/vitalog_roadmap.md) — implementation sequencing.
- [docs/Vitalog_PRD.md](docs/Vitalog_PRD.md) — historical v1. Do not modify or cite for new work.
- [docs/Vitalog_Capstone.md](docs/Vitalog_Capstone.md) — capstone framing doc.

## Stack invariants

Do not re-litigate these without first updating `docs/Vitalog_architecture.md`:

- Python 3.11+, Pydantic for all LLM I/O schemas.
- Anthropic Claude Sonnet via the Anthropic Python SDK. Single-provider for the capstone (architecture ADR-08).
- Interface: MCP via Claude Desktop is the demo channel; CLI is fallback.
- OCR: AWS Textract primary → Claude vision-LLM fallback (architecture ADR-02).
- Persistence: Supabase (Postgres + Storage), Repository pattern.
- All LLM calls pass through the AI Gateway (architecture §7.1).
- Citation verification: Mode A (structured tool-use) for the Summary Generator; Mode B (parse-and-match) for the Observation Generator and NLQ Handler (architecture §7.2.1).

## Code Standards

### Python

- Type hints on every public function signature (parameters + return type). No `Any` without a comment explaining why.
- Pydantic v2 models: `model_config = ConfigDict(strict=True)`. Never `extra="allow"`.
- All LLM calls through `Gateway.call()` — never instantiate `anthropic.Anthropic()` directly outside `src/gateway/`.
- No bare `except:` — catch specific exceptions or `except Exception as e:` with a log statement.
- `ruff check` and `ruff format` must pass before commit (`make lint`).
- `mypy --strict` must pass (`make typecheck`).

### Naming

- Files and modules: `snake_case.py`.
- Classes: `PascalCase`. Pydantic models are classes.
- Prompt files: `prompts/<concern>/<version>.md` (e.g., `prompts/summary/v1.md`).

### Tests

- Unit tests use fixtures from `tests/fixtures/` — no network calls, no Supabase writes.
- Integration tests (marked `@pytest.mark.integration`) may call live Supabase; skip them with `pytest -m "not integration"`.
- Every new public function in `src/` needs at least one test.

## Key files (update as tasks land)

**Built:**
- `src/gateway/gateway.py` — single LLM chokepoint; all external AI calls go here.
- `src/gateway/guardrails/layer1.py` — PHI redactor (log-only) and heuristic injection detector.
- `src/gateway/guardrails/layer2.py` — safety preamble + few-shot refusal loader; prepended to every system prompt.
- `src/gateway/prompt_registry.py` — loads versioned prompt files from `prompts/`; renders templates.
- `src/gateway/eval_logger.py` — writes per-call JSONL to `eval_corpus/runs/`; stores redacted inputs.
- `src/persistence/models.py` — Pydantic models for all DB entities (LabDocument, BiomarkerRecord, etc.).
- `src/persistence/document_repository.py` — CRUD for lab documents.
- `src/persistence/biomarker_repository.py` — CRUD for biomarker records.
- `src/persistence/taxonomy_repository.py` — reads biomarker taxonomy from Supabase.
- `src/persistence/audit_log_repository.py` — append-only audit log with hash chain.
- `src/reference_data/lint.py` — validates `biomarker_taxonomy.json` against the schema.
- `reference_data/biomarker_taxonomy.json` — 30-entry taxonomy seed; source of truth for canonical names, UCUM units, and guideline ranges.
- `prompts/` — versioned prompt files; bump version on any edit.

**Not yet built (future stories):**
- `src/ingestion/classifier.py` — document classification (returns `ClassificationResult`). *(D2)*
- `src/ingestion/structurer.py` — LLM structurer + composite confidence; contains `THRESHOLD_AUTO_ACCEPT` / `THRESHOLD_REJECT` constants. *(D6)*
- `src/normalization/tier1.py` — canonical biomarker alias lookup. *(E1)*
- `src/intelligence/summary_generator.py` — Mode A citation-verified cardiology summary. *(F5)*
- `src/intelligence/observation_generator.py` — Mode B, one-sentence factual observations. *(F2)*
- `src/mcp_server/server.py` — stdio MCP server entry point; registers all six tools. *(G1)*

## Storage policy

Classification-gated per architecture §7.6:

- `lab_report` → retained permanently.
- `recognized_unsupported` → retained permanently with v1+ roadmap message to the user.
- `not_supported` → file discarded after classification; audit metadata only is preserved.

This supersedes the v1 PRD's blanket "never deleted" rule.

## Workflow

Inherits the parent [applications/CLAUDE.md](../CLAUDE.md) plan-mode workflow, with project specifics:

- Always enter plan mode before writing code. Write the plan to `.claude/tasks/<TASK_NAME>.md`.
- Each plan: context, file paths to modify, reasoning, step-by-step tasks, and a verification section.
- Wait for explicit approval before implementing.
- Update the plan file as work progresses; append change descriptions so work can be handed off.
- MVP-focused. If a proposal isn't in architecture §11 capstone scope, flag it as deferred rather than building it.

## Out of capstone scope

Do not propose these unless the user explicitly asks (architecture §12):

- LLM-as-judge guardrail layer (highest-priority deferred safety item).
- Multi-provider failover.
- Web UI.
- Tiers 2 and 3 of biomarker normalization.
- Arithmetic validation on derived values inside Citation Mode A.

## Gotchas

- **Confidence threshold constants live in `src/ingestion/structurer.py`** (`THRESHOLD_AUTO_ACCEPT`, `THRESHOLD_REJECT`). Never change them without re-running `make calibrate` and reviewing `eval_corpus/calibration_report.md`.
- **Prompt versioning is mandatory.** The eval logger stores `(prompt_id, version)` per call. Editing a prompt without bumping the version will silently corrupt eval replay. Version format: `v1`, `v2` — no semver.
- **Mode A vs Mode B.** Summary Generator uses Mode A (every numeric must be wrapped in a `Citation` with `source_record_id`). Observation Generator uses Mode B (parse output numerics, match against retrieval set within ±0.5%). They cannot be swapped.
- **Classification gates storage** (architecture §7.6). A `not_supported` document must never write a row to `biomarker_records` — only an audit log entry. Violating this breaks the privacy model.
- **Mark's patient profile** is hardcoded in `reference_data/mark_profile.json` for the capstone. Do not load it from Supabase unless task 18 (if-time) has landed.

## Common commands

- Tests: `make test` (unit only, skips integration)
- Lint: `make lint` (`ruff check` + `ruff format --check`)
- Format (fix): `make format`
- Type check: `make typecheck` (`mypy --strict src/`)
- Environment: `uv sync`
