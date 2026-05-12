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

## Common commands

Placeholders — update once `pyproject.toml` exists:

- Tests: `pytest -q`
- Lint / format: `ruff check . && ruff format .`
- Type check: `mypy .`
- Environment: `uv sync` (preferred) or `pip install -e .`
