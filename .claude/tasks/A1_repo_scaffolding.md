# A1 — Repo scaffolding & dev tooling

**Epic:** Foundation
**Points:** 3
**Priority:** Critical
**Depends on:** —
**Architecture refs:** project CLAUDE.md (Code Standards, Common commands); architecture §9

## User story

As the founder building Vitalog,
I want a working Python project skeleton with the four-concerns folder layout, strict tooling, and a `make` target for each common task,
So that every subsequent story can `pytest`, `make lint`, `make typecheck` from day one without arguing about layout.

## Why this matters

Project CLAUDE.md hard-requires `ruff check`, `ruff format`, and `mypy --strict` to pass before commit. Setting these up first means every later story inherits the safety net automatically — and the four-concerns folder layout enforces the architectural boundary (ADR-01) by physical separation, not just discipline.

## Acceptance criteria

1. **Given** a fresh clone of the repo, **When** I run `uv sync`, **Then** all dev dependencies install without error and `pyproject.toml` is the single source of truth for them.
2. **Given** the repo at HEAD, **When** I run `make lint`, **Then** `ruff check .` and `ruff format --check .` both pass.
3. **Given** the repo at HEAD, **When** I run `make typecheck`, **Then** `mypy --strict src/` passes (empty modules are fine).
4. **Given** the repo at HEAD, **When** I run `make test`, **Then** `pytest -q` runs (zero or more tests, all green).
5. **Given** the four-concerns architecture, **When** I `ls src/`, **Then** I see `ingestion/`, `normalization/`, `persistence/`, `intelligence/`, `gateway/`, `mcp_server/`, `orchestration/` as separate packages each with `__init__.py`.
6. **Given** the `.env.example` file, **When** I diff it against the code, **Then** every env var read by the code has a commented entry.

## Files to create / modify

- `pyproject.toml` — Python 3.11+, deps: `anthropic`, `pydantic>=2`, `supabase`, `boto3` (Textract), `mcp` (Anthropic Python MCP SDK), `pytest`, `pytest-asyncio`, `ruff`, `mypy`, `reportlab` (for F6 PDF)
- `Makefile` — `lint`, `format`, `typecheck`, `test`, `calibrate`, `eval`
- `.env.example` — `ANTHROPIC_API_KEY`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`
- `.gitignore` — Python + IDE + `.env` + `eval_corpus/runs/`
- `src/__init__.py`, `src/{ingestion,normalization,persistence,intelligence,gateway,mcp_server,orchestration,reference_data}/__init__.py`
- `tests/__init__.py` plus mirroring sub-packages
- `prompts/` directory with `.gitkeep`
- `reference_data/` directory with `.gitkeep`
- `eval_corpus/` directory with `.gitkeep`
- `scripts/` directory with `.gitkeep`
- `ruff.toml` (line length 100, target Py3.11)
- `mypy.ini` — strict mode, ignore_missing_imports for `mcp`, `boto3`

## Implementation notes

- Use `uv` per project CLAUDE.md ("`uv sync` preferred"). Lock file committed.
- `pytest` discovers `tests/`; add `pytest.ini` with `markers = integration` so `pytest -m "not integration"` is the default fast lane.
- `mypy --strict` will complain about untyped third-party packages; whitelist only `mcp`, `boto3`, `anthropic` (the rest must be typed).
- Do NOT install Pydantic v1 — the project standard is v2 with `ConfigDict(strict=True)`.
- The `calibrate` make target is a stub that will be filled by C5; it should at minimum print a "not yet implemented" message and return non-zero so CI fails loudly until C5 lands.

## Verification

- `make lint && make typecheck && make test` — all green from a clean clone
- `python -c "import src.ingestion, src.normalization, src.persistence, src.intelligence, src.gateway, src.mcp_server, src.orchestration"` — all imports succeed
- `uv lock --check` — lock file consistent

## INVEST check

- [x] Independent — no upstream dependencies
- [x] Negotiable — exact dep versions flexible
- [x] Valuable — every later story relies on it
- [x] Estimable — bounded scaffolding work
- [x] Small — 3 pts
- [x] Testable — verifiable via the make targets above

## Deferred (explicitly out of this story)

- CI workflow (`.github/workflows/`) — not in capstone scope; manual local discipline suffices
- Pre-commit hooks — nice-to-have, not in scope
- Docker / containerization — not in scope

## Notes / changelog

_(append after work is done)_
