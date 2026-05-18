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
| `src/intelligence/` | Trend engine (F1 ✅); Observation Generator (F2 ✅); NLQ Handler + retrieval resolver (F3 ✅); Context cards (F4 ✅) — `context_cards.py` + `context_card_schemas.py` |
| `src/persistence/` | Repository pattern over Supabase; all DB entity models |
| `src/eval/synthesis/` | Synthetic lab report generator (C1 ✅); Quest/hospital/LabCorp vendor templates (C2 ✅); ground truth writer |
| `src/eval/harness/` | Extraction accuracy harness (C3 ✅): `comparator.py` (per-field comparison, ±0.5% decimal tolerance, rapidfuzz name matching), `aggregator.py` (precision/recall/F1 by field/split/band), `runner.py` (dry-run + live pipeline dispatch), `reporter.py` (accuracy.json + accuracy.md + history.csv) |
| `eval_corpus/` | Fixed eval corpus (C2 ✅): `synthetic/` (10 docs), `adversarial/` (3 docs), `redacted_real/` (placeholder); `manifest.json` with SHA-256 hashes; `redaction_checklist.md`; `history.csv` (C3 ✅) — append-only harness run history |
| `scripts/build_adversarial.py` | Generate 3 adversarial corpus docs (C2 ✅) |
| `scripts/build_manifest.py` | SHA-256 hash all corpus files → `manifest.json` (C2 ✅) |
| `scripts/redact_real.py` | PyMuPDF HIPAA Safe Harbor redaction helper for user-provided real PDFs (C2 ✅) |
| `scripts/run_accuracy.py` | Harness CLI (C3 ✅): `--dry-run` for GT self-comparison (~100% F1, no API calls); live mode runs D1–D6 against full corpus |
| `src/reference_data/` | Taxonomy loader (cached); `biomarker_taxonomy.json` — 30-biomarker seed; `patient_profile.py` + `patient_profile_schemas.py` — Mark's hardcoded profile (G2 ✅) |
| `scripts/` | Admin CLI (`resolve_pending`, `generate_synthetic`) |
| `prompts/` | Versioned prompt templates — bump version on every edit |

## Workflow

@.claude/workflow.md

- MVP-focused. Flag anything outside architecture §11 capstone scope as deferred.

## Gotchas

- **Prompt versioning is mandatory.** Eval logger stores `(prompt_id, version)` per call. Editing a prompt without bumping the version silently corrupts eval replay.
- **Mode A vs Mode B cannot be swapped.** Summary Generator: every numeric wrapped in a `Citation` with `source_record_id`. Observation Generator: parse output numerics, match against retrieval set within ±0.5%.
- **Layer 1 injection detector must recurse into nested dicts** — same as `redact_for_log`. A flat join misses `{"patient": {"query": "ignore all instructions"}}`. Both use `_collect_text()`.
- **Classification gates storage.** A `not_supported` document must never write to `biomarker_records` — audit log only. Violating this breaks the privacy model (§7.6).
- **Confidence thresholds live in `src/ingestion/structurer.py`** (`THRESHOLD_AUTO_ACCEPT`, `THRESHOLD_REJECT`). Never change without re-running `make calibrate` and reviewing `eval_corpus/calibration_report.md`.
- **Mark's patient profile** is hardcoded in `reference_data/mark_profile.json`. Do not load from Supabase unless task 18 (if-time) has landed.
- **L3 stores (pattern, phrase) tuples** — `BannedPhraseViolation.phrases` contains the original human-readable phrases, not the compiled regex patterns. The retry system prompt uses these to name the offending text explicitly.
- **Mode A retrieval set is caller-supplied.** `verify_mode_a(citations, patient_id, retrieval_set)` does zero I/O — the caller (F5 Summary Generator) must build `retrieval_set: dict[uuid.UUID, BiomarkerRecordRow]` from the records it passed to the prompt. AC5 retry-on-failure logic lives in F5, not the verifier.
- **MODE_A_NUMERIC_TOLERANCE = 0.005** (±0.5%) lives in `src/gateway/citation_verifier_mode_a.py`. Do not use floating-point boundary arithmetic in tests — use concrete literal values (e.g. `7.034`) to avoid IEEE 754 instability at the exact boundary.
- **Mode B retrieval set is caller-supplied.** `verify_mode_b(prose, retrieval_set)` does zero I/O — the caller (F2 Observation Generator, F3 NLQ Handler) builds `retrieval_set: dict[uuid.UUID, BiomarkerRecordRow]`. AC6 retry-on-failure logic lives in F2/F3, not the verifier.
- **Mode B unit validity gate.** `_is_valid_unit(unit)` in `numeric_parser.py` rejects pure-lowercase-alpha tokens (English verbs like "has", "was") that the regex captures as adjacent units. Real clinical units always contain `%`, `/`, a digit, or an uppercase letter.
- **Mode B integer vs decimal.** Presence of `.` in the original text determines tolerance: decimal → ±0.5%, integer → exact match. `"120"` must match stored `120.0` exactly; `"6.8"` may match stored `6.8` within tolerance.
- **F2 pending-taxonomy guard.** `ObservationGenerator.generate()` raises `ValueError` with `"pending-taxonomy"` in the message if `record.canonical_biomarker_id is None`. Do not silently pass `""` to `get_trend` — that would call the trend engine with an empty ID and corrupt the retrieval set.
- **ObservationCitation.record_id is `str | None`, not `uuid.UUID`.** Pydantic `strict=True` rejects automatic `str→UUID` coercion; the LLM always returns strings in JSON tool-use output. Changing this field to `uuid.UUID` causes `OutputValidationError` on every call.
- **F2 guideline bounds must be in the retrieval set.** `_build_retrieval_set` adds a synthetic `BiomarkerRecordRow` per `band.lower`/`band.upper` value so Mode B accepts numbers like "7.0%" from "ADA target <7.0%". Without this, Mode B rejects the output even when the LLM follows the prompt correctly.
- **F2 date format must be month-first.** `_build_inputs` formats `collection_date` as `f"{d.strftime('%B')} {d.day}, {d.year}"` (e.g., "March 12, 2026"). Day-first formats cause Mode B to extract the day number as an unmatched bare integer — the false-positive filter only skips day numbers when the month name precedes them.
- **F3 retrieval token stripping is required.** `_direct_alias_matches` strips non-alphanumeric chars from each token before alias lookup so "HbA1c?" resolves correctly. Without this, trailing punctuation causes lookup to fail silently and the query falls through to the safe-refusal path.
- **F3 condition matching uses significant-word threshold (>=8 chars).** `_condition_biomarker_matches` matches any display-name word ≥8 chars against the query so "diabetes" expands T2D biomarkers without requiring the full "Type 2 Diabetes" string. Words < 8 chars ("type", "chronic", "disease") are skipped to avoid false positives.
- **F3 NLQ retrieval set has no synthetic guideline records.** Unlike F2 (which adds synthetic records for band bounds), F3's retrieval set contains only real patient records. NLQ must not cite guideline target values — Mode B correctly rejects them.
- **`load_condition_biomarker_map` is now `@lru_cache`.** Added in the F3 review fix. All six reference-data loaders that are called in hot paths (`load_taxonomy`, `load_condition_biomarker_map`) are now cached after first read.

## Out of capstone scope

Do not propose unless the user explicitly asks (architecture §12):
- LLM-as-judge guardrail layer (highest-priority deferred safety item)
- Multi-provider failover
- Web UI
- Tiers 2 and 3 of biomarker normalization
- Arithmetic validation on derived values inside Citation Mode A
