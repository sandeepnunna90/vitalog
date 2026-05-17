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

**Built (Epic A–D):**
- `src/ingestion/errors.py` — `IngestionError` base + `UnsupportedFormatError(detected_mime)`, `FileTooLargeError(size_bytes, max_bytes)`, `CorruptOrEmptyError(reason)`
- `src/ingestion/probes.py` — `probe_pdf(file_bytes) -> bool` (PyMuPDF text extractability); `probe_image(file_bytes, mime) -> str | None` (resolution warning if <600×600); both use deferred imports
- `src/ingestion/upload_validator.py` — `ValidatedUpload` Pydantic model; `UploadValidator` with 6-step pipeline (empty → MIME → support → size → integrity → probes); `_detect_mime()` with puremagic + raw-byte HEIC fallback; `try/except/finally` audit pattern
- `src/ingestion/__init__.py` — exports all ingestion public API
- `tests/ingestion/conftest.py` — 10 programmatic fixtures (no committed binaries)
- `src/ingestion/classification_schemas.py` — `Category` + `Subtype` StrEnums; `ClassificationResult` Pydantic model with `Field(ge=0.0, le=1.0)` on confidence and `Field(min_length=1)` on reasoning
- `src/ingestion/classifier.py` — `DocumentClassifier`; PDF text via PyMuPDF (early-exit accumulator, 8k char limit); image via base64 vision block; conservative bias override at confidence < 0.70; defensive `fitz.open()` guard
- `src/ingestion/user_messages.py` — `get_user_message()` returns §5.1 message templates by category/subtype
- `prompts/classification/v1.md` — classification prompt (Haiku); full v1 subtype taxonomy; conservative bias rules verbatim in system prompt
- `tests/ingestion/test_classifier_unit.py` + `test_classifier_messages.py` — 16 tests; all Gateway calls mocked
- `src/ingestion/storage_router.py` — `StorageRouter` + `StorageRouteResult`; routes on `ClassificationResult.category`; `not_supported` → `discard_after_classification` (no doc row); reasoning truncated to 500 chars in audit; partial-failure gap documented as known capstone limitation
- `src/ingestion/orchestration_hook.py` — `IngestionOrchestrator` + `IngestionResult`; wires validator → classifier → router; `textract_fn` slot for D4; short-circuit enforced via `should_continue_pipeline`; explicit `RuntimeError` guard on `document_id`
- `tests/ingestion/test_storage_router.py` + `test_short_circuit.py` — 18 tests; all three routing branches + error paths + PRD Scenarios 9 & 10
- `src/ingestion/textract_schemas.py` — `BoundingBox`, `Block`, `TableCell`, `Table`, `KVPair`, `TextractResult` Pydantic models; all confidence fields annotated as Textract-native 0–100 scale
- `src/ingestion/textract_adapter.py` — `TextractAdapter`; calls `AnalyzeDocument(FORMS+TABLES)` synchronously; normalizes verbose Textract response into typed schemas; retries throttle/5xx with exp. backoff (0s/1s/2s); `NoCredentialsError` non-retryable; merged-cell silent overwrite documented as known capstone limitation; writes `textract_extracted` audit entry with latency + confidence stats
- `src/ingestion/errors.py` — `TextractFailureError(reason, attempt_count)` added
- `tests/ingestion/test_textract_adapter.py` — 12 unit tests (boto3 mocked via `client=` injection); 1 integration test (skips if `AWS_ACCESS_KEY_ID` unset); covers all 6 ACs + BotoCoreError retry path
- `runs/cost_notes.md` — Textract free-tier cost note
- `src/ingestion/textract_fallback.py` — `TextractFallbackAdapter`; compares `min_confidence` of `TextractResult` against `THRESHOLD_FALLBACK` (95.0); sends document image to Claude vision via `Gateway.call("extraction", "v1")`; PDF rendered to PNG with PyMuPDF; normalizes `FallbackExtractionResult` back to `TextractResult` (uniform interface for D6); writes `vision_fallback_skipped` or `vision_fallback_invoked` audit entry
- `prompts/extraction/v1.md` — vision extraction prompt; instructs Claude to transcribe-only (no inference), report per-field confidence 0–100, use `[unreadable]` for unclear text
- `tests/ingestion/test_textract_fallback.py` — 15 unit tests; Gateway and AuditLogRepository mocked; covers threshold boundary, all audit paths, result conversion, image content building (JPEG/PDF/HEIC), error propagation
- `src/ingestion/structurer_schemas.py` — `Band` StrEnum; `RawBiomarkerCandidate` (LLM output); `StructuredReport` (Gateway schema); `BiomarkerCandidate` (public output with `composite_confidence` + `band`)
- `src/ingestion/composite_confidence.py` — `compute_composite(textract, llm, classification)` scales classification 0-1→0-100; returns `min()` of three signals
- `src/ingestion/band_router.py` — `assign_band(composite, threshold_auto_accept, threshold_reject) → Band`; thresholds passed in, not hard-coded
- `src/ingestion/structurer.py` — `Structurer` + `THRESHOLD_AUTO_ACCEPT=95.0` / `THRESHOLD_REJECT=70.0` named constants; `_serialize_textract_result` flattens KV/tables/blocks; `_compute_textract_floor` uses global OCR min
- `prompts/structurer/v1.md` — Sonnet, 4096 tokens, 3 in-prompt examples; "Structure ONLY what is visible" hard constraint
- `tests/ingestion/test_structurer.py` + `test_composite_confidence.py` + `test_band_router.py` — 35 tests; Gateway and audit mocked; classification-as-floor scenarios covered

**Built (Epic A–B):**
- `src/gateway/gateway.py` — single LLM chokepoint; wires Layer 1 + Layer 2; renders templates with original inputs; logs only redacted inputs
- `src/gateway/anthropic_adapter.py` — SDK adapter; exponential-backoff retry; catches `RateLimitError`, `APIStatusError`, `APIConnectionError`; one schema-enforcement retry per call
- `src/gateway/guardrails/layer1.py` — PHI redactor (log-only, recurses into nested dicts) + heuristic injection detector (warns, never blocks)
- `src/gateway/guardrails/layer2.py` — safety preamble + few-shot refusal loader; prepended to every system prompt via `Layer2.augment_system()`
- `src/gateway/guardrails/layer3_deterministic.py` — schema validator (wraps Pydantic) + banned-phrase scanner; loaded from `prompts/_shared/banned_phrases.txt`; one retry on failure
- `src/gateway/errors.py` — typed exception hierarchy: `BannedPhraseViolation(phrases)`, `SchemaValidationError(field_errors)`, `OutputValidationError`, `ModelError`
- `prompts/_shared/banned_phrases.txt` — 25 banned clinical-advice phrases; case-insensitive `\b`-bounded match
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

**Built (Epic E):**
- `src/normalization/index_builder.py` — `_normalize_key()` (lowercase + whitespace collapse + parenthetical strip) + `build_index()` (raises ValueError on duplicate alias across entries)
- `src/normalization/tier1.py` — `lookup(raw_name) -> str | None`; O(1) lru_cached index built from `load_taxonomy()`; only public entry point
- `src/normalization/__init__.py` — exports `lookup`
- `tests/normalization/test_tier1.py` — 303 tests; all 30 canonical names + all aliases (parametrized), case folding, whitespace, parentheticals, unknown→None, duplicate detection

**Built (Epic C):**
- `src/eval/synthesis/content_generator.py` — 16-biomarker `BIOMARKER_RANGES` dict; `generate_readings(seed, overrides)` via `random.Random(seed)`; `overrides` kwarg for H1 hero dataset pins
- `src/eval/synthesis/ground_truth_writer.py` — `write_ground_truth()` emits paired JSON with all AC3 fields
- `src/eval/synthesis/vendor_templates/quest.py` — reportlab Quest-style PDF renderer; `_make_reproducible()` patches `/CreationDate`, `/ModDate`, `/Producer`, `/Creator`, `/ID` in raw bytes for byte-identical output; `generate_report(seed, out_dir, *, collection_date, lab_source, overrides)` creates `out_dir` if needed
- `src/eval/synthesis/__init__.py` — exports `generate_report`
- `scripts/generate_synthetic.py` — CLI `--vendor quest --count --seed --out`
- `tests/eval/test_synthesis_reproducibility.py` + `test_ground_truth_invariants.py` — 18 tests; reproducibility, AC3 field invariants, custom params, overrides, filename format

**Up next (Epic E–F):**
- `src/normalization/` — E2 pending queue, E3 unit conversion, E4 dedup
- `src/intelligence/summary_generator.py` — Mode A citation-verified summary *(F5)*
- `src/intelligence/observation_generator.py` — Mode B factual observations *(F2)*
- `src/mcp_server/server.py` — stdio MCP server, 6 tools *(G1)*

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

## Out of capstone scope

Do not propose unless the user explicitly asks (architecture §12):
- LLM-as-judge guardrail layer (highest-priority deferred safety item)
- Multi-provider failover
- Web UI
- Tiers 2 and 3 of biomarker normalization
- Arithmetic validation on derived values inside Citation Mode A
