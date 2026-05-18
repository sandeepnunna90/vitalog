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

## Module map

| Package | Purpose |
|---|---|
| `src/ingestion/` | Upload validation, classification, Textract/vision OCR, structurer, composite confidence |
| `src/gateway/` | AI Gateway chokepoint, guardrails (L1/L2/L3), prompt registry, eval logger, Mode A + Mode B citation verifiers |
| `src/normalization/` | Tier 1 alias lookup, unit conversion, range validation, duplicate detection |
| `src/intelligence/` | Trend engine (F1 ✅); Observation Generator (F2 ✅); NLQ Handler + retrieval resolver (F3 ✅); Context cards (F4 ✅) — `context_cards.py` + `context_card_schemas.py`; Summary Generator (F5 ✅) — `summary_generator.py` + `summary_schemas.py`; Annotation + Export (F6 ✅) — `annotator.py`, `export_schemas.py`, `exporter.py`, `exporters/pdf_exporter.py`, `exporters/markdown_exporter.py`, `exporters/json_exporter.py` |
| `src/persistence/` | Repository pattern over Supabase; all DB entity models |
| `src/eval/synthesis/` | Synthetic lab report generator (C1 ✅); Quest/hospital/LabCorp vendor templates (C2 ✅); ground truth writer |
| `src/eval/harness/` | Extraction accuracy harness (C3 ✅): `comparator.py` (per-field comparison, ±0.5% decimal tolerance, rapidfuzz name matching), `aggregator.py` (precision/recall/F1 by field/split/band), `runner.py` (dry-run + live pipeline dispatch), `reporter.py` (accuracy.json + accuracy.md + history.csv) |
| `eval_corpus/` | Fixed eval corpus (C2 ✅): `synthetic/` (10 docs), `adversarial/` (3 docs), `redacted_real/` (placeholder); `manifest.json` with SHA-256 hashes; `redaction_checklist.md`; `history.csv` (C3 ✅) — append-only harness run history |
| `scripts/build_adversarial.py` | Generate 3 adversarial corpus docs (C2 ✅) |
| `scripts/build_manifest.py` | SHA-256 hash all corpus files → `manifest.json` (C2 ✅) |
| `scripts/redact_real.py` | PyMuPDF HIPAA Safe Harbor redaction helper for user-provided real PDFs (C2 ✅) |
| `scripts/run_accuracy.py` | Harness CLI (C3 ✅): `--dry-run` for GT self-comparison (~100% F1, no API calls); live mode runs D1–D6 against full corpus |
| `src/reference_data/` | Taxonomy loader (cached); `biomarker_taxonomy.json` — 30-biomarker seed; `patient_profile.py` + `patient_profile_schemas.py` — Mark's hardcoded profile (G2 ✅); `biomarker_groups.json` — 9-condition grouping reference with embedded guideline citations (F5 ✅) |
| `scripts/` | Admin CLI (`resolve_pending`, `generate_synthetic`) |
| `prompts/` | Versioned prompt templates — bump version on every edit |

## Workflow

@.claude/workflow.md

- MVP-focused. Flag anything outside architecture §11 capstone scope as deferred.

## Gotchas

@.claude/gotchas.md

## Out of capstone scope

Do not propose unless the user explicitly asks (architecture §12):
- LLM-as-judge guardrail layer (highest-priority deferred safety item)
- Multi-provider failover
- Web UI
- Tiers 2 and 3 of biomarker normalization
- Arithmetic validation on derived values inside Citation Mode A
