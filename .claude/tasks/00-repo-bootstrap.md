# Task 00 — Repo bootstrap

## Context

No application code exists yet. Every downstream task assumes a Python project with a four-concerns folder layout, a working `uv` env, ruff/mypy/pytest, and an `.env.example`. This task makes that real.

## Dependencies

None.

## In scope

- `pyproject.toml` (uv-managed) with deps: `anthropic`, `pydantic>=2`, `boto3` (Textract), `supabase`, `python-dotenv`, `reportlab`, `weasyprint` (PDF render for synthetic corpus), `pytest`, `pytest-asyncio`, `ruff`, `mypy`, `types-boto3-textract`.
- Folder structure mirroring architecture §5 four-concerns separation:
  - `src/ingestion/`, `src/normalization/`, `src/persistence/`, `src/intelligence/`
  - `src/gateway/` (AI Gateway lives in its own concern)
  - `src/mcp_server/`
  - `src/schemas/` (shared Pydantic models)
  - `prompts/` (versioned prompt registry)
  - `reference_data/` (LOINC, UCUM, taxonomy seed, guideline ranges)
  - `eval_corpus/` (synthetic docs + ground truth + adversarial prompts)
  - `migrations/` (SQL files for Supabase)
  - `scripts/` (generators, calibration, admin)
  - `tests/` mirroring `src/`
- `README.md` skeleton: project blurb, quickstart (`uv sync`, env vars, run MCP), pointers to PRD v2 / architecture / roadmap, demo flow.
- `.env.example` with `ANTHROPIC_API_KEY`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `VITALOG_ENV`.
- `.gitignore` (Python, env files, eval_corpus PDFs but commit ground-truth JSON, Supabase artifacts).
- `ruff.toml` / `pyproject` ruff config: line length 100, `E,F,I,B,UP` rules, format on save.
- `mypy.ini`: strict on `src/`, lenient on `tests/` and `scripts/`.
- `Makefile` with `make test`, `make lint`, `make typecheck`, `make demo`.
- `__init__.py` files in every package.

## Out of scope (deferred)

- Pre-commit hooks (nice-to-have; defer to if-time).
- CI/CD (no GitHub Actions for capstone).
- Docker (defer to v1.5).

## Files to create

- `pyproject.toml`
- `README.md`
- `.env.example`
- `.gitignore`
- `ruff.toml`
- `mypy.ini`
- `Makefile`
- `src/**/__init__.py` (one per package above)
- `tests/__init__.py`

## Architecture references

- `docs/Vitalog_architecture.md` §5 — four-concerns separation
- `docs/Vitalog_architecture.md` §9 — technology choices
- `docs/vitalog_roadmap.md` §4 "Repo and tooling" — folder layout expectation

## Step-by-step

1. `uv init` at project root; choose package layout.
2. Add deps via `uv add <pkg>`; pin majors only.
3. Create the folder tree above with empty `__init__.py` files.
4. Write README skeleton with sections: Overview, Architecture (link), Setup, Demo flow, Status.
5. Write `.env.example`; never commit a real `.env`.
6. Configure ruff (`line-length=100`, `select=["E","F","I","B","UP"]`) and mypy (`strict = True` for `src/`).
7. Write `Makefile` targets: `test`, `lint`, `format`, `typecheck`, `demo` (the last is a placeholder).
8. Run `make lint && make typecheck` — both should pass on an empty src.

## Acceptance criteria

- [ ] `uv sync` runs clean.
- [ ] `make lint` passes (no source files yet).
- [ ] `make typecheck` passes.
- [ ] `tree -L 2 -I '__pycache__'` shows the four-concerns layout.
- [ ] `README.md` references PRD v2, architecture doc, roadmap by relative path.
- [ ] `.env.example` exists; no real secrets in repo.

## Verification

- `uv sync && make lint && make typecheck`
- `git status` shows only intended files.
- Open `README.md` in a viewer; links resolve.
