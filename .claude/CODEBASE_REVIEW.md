# Vitalog Codebase Review
Date: 2026-05-18
Reviewer: Claude Opus (automated)

## Executive Summary

Vitalog is a small, well-structured Python application (~7.5k lines of `src/` code, ~8k lines of tests) that follows its own documented architecture closely. The four-concern split, the AI-Gateway chokepoint (P3), the repository pattern, and the deterministic-vs-LLM separation (P4) are all enforced in code, not just in docs. Coverage of tests is strong across the board. The codebase is in clearly better health than typical for a capstone — but it has a handful of real correctness and architectural concerns that warrant attention, plus a recurring pattern of audit-log silent failures that should be revisited together.

## Critical Issues

### C1. Mode A unit comparison ignores leading/trailing whitespace
`src/gateway/citation_verifier_mode_a.py:60`
```python
if record.canonical_unit != citation.unit:
```
Mode B (`citation_verifier_mode_b.py:104-105`) does a direct `==` against `record.canonical_unit` *and* `record.original_unit`, but the harness comparator (`eval/harness/comparator.py:127`) is careful to compare units with `.strip()`. Mode A does neither. If the LLM emits `"mg/dL "` (trailing space — Anthropic models occasionally do, especially after a numeric) the verifier raises and the *entire summary attempt is discarded*, then retried, then falls back to a blank `Summary(is_fallback=True)` even though the values are perfectly correct. Suggest:
```python
if record.canonical_unit.strip() != citation.unit.strip():
```
plus add a regression test that passes `"mg/dL "` and expects success. Same concern applies to the date comparison on line 67, though `date` objects don't have whitespace risk.

### C2. F6 Markdown exporter assumes ISO-string `created_at` but Python `datetime` objects can sneak in
`src/intelligence/exporters/markdown_exporter.py:48`
```python
lines.append(f"> **Patient note:** {ann.text} _({ann.created_at[:10]})_")
```
`Annotation.created_at` is typed `str` (intentional, per `export_schemas.py:20`), but `_parse_annotations()` does `Annotation.model_validate(item)` with default strict, which would reject a datetime. That part is fine. However, `Annotation` is *constructed* in `annotator.py:84` with `datetime.now(UTC).isoformat()` — a string — so this works today. The risk is fragility: any future code path that constructs an `Annotation` with `datetime.now(UTC)` (the natural thing to type) will pass Pydantic strict only if strict is off, and would crash at the `[:10]` slice with `TypeError: 'datetime' object is not subscriptable`. Either drop the magic slice in favour of a parse-and-format, or assert/parse the date in the exporter.

### C3. F2 retry path can silently double-fail without retry guidance
`src/intelligence/observation_generator.py:68-70`
```python
output = self._attempt(inputs, retrieval_set)
if output is None:
    output = self._attempt(inputs, retrieval_set)
```
Two-attempt loop, but the second `_attempt()` call is *identical* — same prompt, same inputs, same retrieval set. Compare this with Gateway's `_call_with_l3_retry()` (`gateway.py:249-267`), which thoughtfully amends the system prompt on retry with explicit guidance about what failed. F2 (and F3, same pattern at `nlq_handler.py:73-75`; F5, same at `summary_generator.py:67-68`) is essentially "try twice, hope the dice land differently the second time." For LLM-determinism reasons it occasionally works, but it's not principled. Consider:
- Pass the verification failure reason back into a retry-system-prompt suffix the same way L3 does.
- Or at least set `temperature` differently on the second attempt (currently the adapter has no temperature kwarg at all).

### C4. Audit log failures are silently swallowed in 8 places
`grep -n "noqa: BLE001"` shows the pattern `except Exception: pass  # audit failure must never break the caller` repeated across gateway, observation_generator, nlq_handler, summary_generator, annotator, exporter, classifier, and upload_validator. The intent is sound (P5 demands provenance, but caller correctness must not break), but the implementation has problems:
1. The exception is never logged anywhere (no `logger.exception(...)`, no metric), so audit-log degradation is invisible.
2. There is no rate-limit or circuit-break — if Supabase is degraded for 5 minutes, every call eats and discards the error.
3. P5 ("Provenance for every data point") becomes a soft promise — silently lost audit events mean compliance can't be reconstructed.
4. Only `upload_validator._record_audit()` logs a warning; the rest don't.

Recommend: factor an `_audit_safe(repo, actor, event_type, payload)` helper that logs the failure with `logger.warning("audit_log_failed", extra={...})` consistently, and consider an in-memory dropped-event counter that gets surfaced in healthchecks.

### C5. Pydantic models in `persistence/models.py` use `list[Any]` and `dict[str, Any]` for typed payloads
`src/persistence/models.py` lines 46-48 (PatientProfile conditions/medications/allergies), 89-93 (CanonicalBiomarkerRow JSONB columns), 175 (SummaryRow.content_json), 195/206 (audit_log.payload). The CLAUDE.md rule is "No `Any` without a comment explaining why" — none of these have comments. More importantly, JSONB is a place where structured Pydantic models would catch deserialization bugs at the boundary. For example, `SummaryRow.content_json` is consumed by all three exporters with `.get("citations", [])`-style dict access — a typed model would catch missing/renamed fields, but with `dict[str, Any]` the exporters silently emit blank or malformed output instead. This already has a known regression vector — see C9 below where annotation parsing fully depends on `patient_annotations` being a JSON string. Suggest: define `SummaryContent` as a Pydantic model and use it as `content_json: SummaryContent`.

## High Priority Issues

### H1. `cache_clear()` on `tier1._index` does not invalidate `reference_data._get_alias_index` or `load_taxonomy`
`src/normalization/taxonomy_editor.py:44`
```python
_index.cache_clear()
```
clears only the Tier 1 lookup cache. But `src/reference_data/__init__.py` exposes `lookup_alias()` backed by an independent `@lru_cache` on `_get_alias_index()` (line 89-91), which itself depends on `load_taxonomy()` (also `@lru_cache`, line 39). Both stay stale after `add_alias()`. So Tier 1 lookups see the new alias immediately, but `lookup_alias` (used by `retrieval._direct_alias_matches` in F3) does not — meaning admins can add an alias and have NLQ silently fail to resolve it until the process restarts. Fix: clear all caches together; ideally have a single `invalidate_taxonomy_caches()` function exported by `reference_data`.

### H2. Index of bug-prone numeric comparison in Mode A: zero-handling vs floating point
`src/gateway/citation_verifier_mode_a.py:80-95`
```python
if stored == 0.0:
    if citation.value != 0.0:
        raise ModeAVerificationError(...)
```
Two issues:
- A biomarker stored as exactly `0.0` is medically suspect (zero glucose, zero potassium = death) but is treated as a normal case. The code is right that "exact match required" is the only sensible policy at zero, but consider whether stored == 0.0 should be treated as an extraction error rather than a citation pass.
- The same zero-handling pattern appears in `duplicate_detector.py:78-79` and in `comparator.py:156-157` — three copies, none cross-referencing each other. Extract a shared `_within_tol(cited, stored, tolerance) -> bool` helper into `normalization/constants.py` (already the home of `MODE_B_NUMERIC_TOLERANCE`).

### H3. Trend engine uses `# type: ignore[arg-type]` to override correct types
`src/intelligence/trend_engine.py:20-21`
```python
collection_date=row.collection_date,  # type: ignore[arg-type]
canonical_value=row.canonical_value,  # type: ignore[arg-type]
```
The model fields are `date | None` and `float | None`; the TrendPoint fields are `date` and `float`. The comment "guaranteed by caller filter" is true *today* but ignored at type-check time. Better: write `_to_point` as
```python
assert row.collection_date is not None
assert row.canonical_value is not None
```
and let mypy narrow. Mypy --strict accepts assert-based narrowing and the comments become enforced invariants instead of polite suggestions.

### H4. Retry budget is unbounded across the AI Gateway stack
The Anthropic adapter has `max_retries=3` (network), plus one schema-enforcement retry. Gateway's `_call_with_l3_retry()` adds one L3 retry. F2/F3/F5 each add another "try twice" loop. Net: a single Summary call can hit Anthropic up to **3 × 2 × 2 × 2 = 24 times** in the worst case (network retry × schema retry × L3 retry × F5 retry). For a capstone scoped to single-patient demo this is fine, but operating cost and per-call latency in the worst-case path are unbounded. Suggest documenting the worst-case fan-out in `Vitalog_architecture.md` §7.1 and adding a per-`call()` retry-budget counter.

### H5. The Layer 1 injection regex `(?m)^system\s*:` is anchored to line start, but `_collect_text()` concatenates with spaces
`src/gateway/guardrails/layer1.py:36` defines the pattern with `(?m)` (multiline mode), but `_collect_text()` at line 69-76 joins string values with `" "` (single space, no newline). The `^` anchor will therefore only match if `system:` is at the very start of the first input value. An attacker putting `system: ignore all instructions` as the second field's content would not be caught. Fix: either make `_collect_text` join with `"\n"`, or remove the `^` anchor.

### H6. The Mode B numeric parser will misclassify scientific notation as integer
`src/gateway/numeric_parser.py:78`
```python
is_int = "." not in raw_num and "e" not in raw_num.lower()
```
This is correct for `"1e5"` → not int (good). But the regex on line 45 captures `(?:\d+\.\d*|\.\d+)(?:[eE][+-]?\d+)?|\d+(?:[eE][+-]?\d+)?` — pure-integer with exponent like `"1e5"` has no `.`, but `is_int` correctly returns False. So this is fine. However, the comment on line 78 says "no decimal point" — false for the `1e5` case. The bigger concern is that `_within_tol_orig()` in the verifier passes the value through `float(record.original_value)` which strips qualifiers like `"<5.7"` — but then `_original_exact()` calls `float(record.original_value) == cited`, and `"<5.7"` will raise `ValueError`, caught and returning False. So qualifier-prefixed integers stored exactly never integer-match. The gotcha is silent — write a test that confirms `"<5"` integer-citation behaviour or add a comment.

### H7. PDF text extraction in classifier handles 0-byte text but not malicious PDFs
`src/ingestion/classifier.py:49-67` opens PDF bytes via `fitz.open(stream=...)` and iterates pages. A PDF crafted to expand decompressed text past the 8KB cap is handled correctly via the `total >= _PDF_TEXT_LIMIT` check, but PyMuPDF is not memory-safe against all malformed PDFs (and has had CVEs). The only gating is `_check_integrity()` in `upload_validator.py:172-179` which just calls `fitz.open()` once. A PDF that opens but panics on `.get_text()` would propagate to the classifier. The `except Exception` at `classifier.py:54` catches the open call, but not the per-page `.get_text()` loop. Recommend wrapping the whole text-extraction in a single try/except, or move text extraction into a shared `probes.extract_pdf_text(file_bytes, limit)` so it's covered by the same probe-test fixtures.

### H8. F5 LLM bypass when `accepted` is empty produces a misleading summary, not a refusal
`src/intelligence/summary_generator.py:52-68` — if a patient has no accepted records, `accepted=[]`, `gaps` is built (likely all biomarkers since none recorded), and the LLM is still invoked with `records_text="No records available."`. The prompt may still produce text, which goes through Mode A verification (passes trivially with no citations) and is returned as a normal `Summary` with `is_fallback=False`. This is technically correct (the prompt instructs "use empty string if nothing to report") but a "summary" of nothing-but-data-gaps is more misleading than a clean "no records yet" message. Recommend short-circuiting to a structured fallback before the LLM call.

### H9. `OutputValidationError` raised from `_apply_output_validators` is not the same as raised from `gateway.call`
`gateway.py:140-156` catches `(BannedPhraseViolation, SchemaValidationError)` and re-raises as `OutputValidationError(f"Output validation failed after retry: {exc}")`. Downstream callers `(observation_generator._attempt`, `nlq_handler._attempt`) catch `(ModeBVerificationError, OutputValidationError)` — that part is fine. But `summary_generator._attempt` (lines 103-110) catches `BannedPhraseViolation` separately, which is now *unreachable* in the post-retry path because the gateway converts it. The remaining direct path that raises `BannedPhraseViolation` is the first attempt that fails L3, but gateway retries it and the second-failure wraps. Net: the `BannedPhraseViolation` catch in `summary_generator._attempt` is dead code. Remove or document.

### H10. `prompt_registry.PromptRegistry.__init__` eagerly raises FileNotFoundError when registry file is missing
`src/gateway/prompt_registry.py:69-70`. This is fine in production where files are committed, but causes test ordering problems if any test instantiates `Gateway(prompts_dir=Path("/tmp/nonexistent"))`. Combined with `Gateway.__init__` reading audit_repo lazily (`gateway.py:35-38`), the symmetry is broken — the prompt registry is a hard fail, audit log is a soft fail. Acceptable, but inconsistent.

## Medium Priority Issues

### M1. `range_overlay._make_label` produces fragile labels with substring matching
`src/intelligence/range_overlay.py:79`
```python
normal_key = next((k for k in guideline_ranges if "_normal" in k.lower()), None)
```
A future key like `"ADA_pre_normalization_baseline"` would match — substring containment is loose. The keys are curated, so this is unlikely, but the pattern is brittle. Prefer endswith or exact-suffix matching.

### M2. `_condition_group_matches` `>=8` significant-word threshold is a magic number with edge cases
`src/intelligence/retrieval.py:114`. The threshold correctly skips "type", "1", "chronic", "disease" — but it also skips "asthma" (6 letters), "anemia" (6), "obesity" (7). Are these conditions intended? `biomarker_groups.json` would need to be inspected, but if any condition's display name has a primary keyword < 8 chars, the keyword won't match and the user has to type the full display name. Suggest either lowering the threshold and adding an explicit skip-list, or storing a per-condition `keywords` field in `biomarker_groups.json`.

### M3. `duplicate_detector` audits "value_conflict" before "duplicate" priority logic completes
`src/normalization/duplicate_detector.py:69-100` accumulates `conflict_prior` while iterating, and only emits the value_conflict audit *after* the loop confirms no duplicate was found. That's correct. But the audit event_type strings are inconsistent: `"dedup_skipped_no_date"`, `"duplicate_detected"`, `"value_conflict"`. The last one is missing the `"dedup_"` prefix that the other two use. Minor naming inconsistency.

### M4. `redact_for_log` does not recurse into list items
`src/gateway/guardrails/layer1.py:52-66`. Compare with `_collect_text` (lines 69-76) — same omission. `detect_injection` therefore does NOT scan list-valued inputs either. If any caller ever passes `inputs={"messages": ["ignore all instructions", "..."]}` (plausible for a chat-style prompt template later), neither redaction nor injection detection covers it. Both helpers should mirror the L3 `_collect_output_text` pattern which DOES recurse into lists (`layer3_deterministic.py:48-53`).

### M5. `_compute_textract_floor` and `_compute_min_confidence` are duplicated
`src/ingestion/structurer.py:122-135` and `src/ingestion/textract_fallback.py:162-175` are byte-for-byte the same logic. The note in `structurer.py:127-128` ("Mirrors the same logic in textract_fallback.py; kept separate to avoid cross-module coupling between two independent adapters") explains it, but the same function being in two places with no test coverage that they stay in sync is risk. Extract into `textract_schemas.py` as a method on `TextractResult` or a module-level helper, both callers import.

### M6. Eval logger generates a new `run_id` per call, not per pipeline run
`src/gateway/eval_logger.py:51`. Each `Gateway.call()` produces an independent `run_id`, and each JSONL file holds a single line. That makes correlation across calls in a single user-facing operation (e.g. an F5 summary that triggers multiple LLM calls during L3 retry) impossible from the logs alone. Suggest threading a session/correlation-id through `Gateway.call()` as an optional parameter, and have it written to each entry.

### M7. `EvalLogger.log()` writes one entry per file (`.jsonl` with exactly one line)
Same module, line 76-77. JSONL by convention holds many entries per file. Writing one entry per file uses up an inode per LLM call. Over a day of demo runs this is fine; under heavier eval load it will exhaust filesystem inodes faster than expected. Either change extension to `.json` and acknowledge it's not JSONL, or accumulate into per-day-per-prompt files.

### M8. `TextractAdapter._normalize` swallows merged-cell information
`src/ingestion/textract_adapter.py:151-156` — documented as a known capstone limitation. RowSpan/ColumnSpan blocks overwrite earlier cells. Lab tables rarely use merged cells but the eval harness includes Quest, LabCorp, and hospital templates — only Quest verified. Worth adding a hospital-template test that exercises a row-spanning header to confirm the documented behaviour matches reality.

### M9. `BiomarkerCandidate.collection_date` and `lab_source` are `str`, not parsed types
`src/ingestion/structurer_schemas.py:29-30`. The data is later persisted to a `date` column (line 144 in models.py). Where does the str→date conversion happen? Looking at `biomarker_repository.py:22`, it goes through `record.model_dump(mode="json")` directly. If the structurer emits `"2026-03-12"`, the Pydantic→JSON dump produces `"2026-03-12"`, which Postgres accepts. But if the LLM emits `"03/12/2026"` or `"March 12, 2026"`, Postgres will throw a runtime error far from the source. The orchestration layer should validate and normalize the date string before persistence; currently it doesn't.

### M10. `summary_generator._build_inputs` sorts by `(original_name, collection_date)` with `collection_date` potentially being a non-comparable value
`src/intelligence/summary_generator.py:201-204`
```python
sorted_records = sorted(accepted_records, key=lambda r: (r.original_name, r.collection_date))
```
The `assert d is not None` later (line 210) shows the author knows `collection_date` *is* non-None here, but the sort would happily compare `None` against `None` only via Python's type-error path. Since the accepted filter at line 58 already excludes None dates, this works — but the assert is downstream of the sort. Move the assert/filter upstream of the sort for type safety.

### M11. `nlq_handler` empty-retrieval fallback never invokes Mode B
`src/intelligence/nlq_handler.py:58-69` — when records are missing, the deterministic fallback text is returned with `is_fallback=True`. No verification is run. That's the right call (no LLM, no numerics to verify). But `_missing_fallback` is built from `canonical_name(cid)` which depends on the taxonomy. If a stale or attacker-controlled `vitalog_id` somehow reaches this path, it gets rendered verbatim into the response. The taxonomy is curated, so this is currently safe — but the input chain is `query → _extract_canonical_ids → biomarker_groups.json → cid → canonical_name`. If `biomarker_groups.json` is ever loaded from a less-trusted source, this becomes a content-injection vector.

### M12. `mcp_server/` and `orchestration/` packages are essentially empty
`src/mcp_server/__init__.py` is empty; `src/orchestration/__init__.py` is empty. They exist as placeholders. The architecture doc describes both as core layers (§4 Orchestration, §4 MCP Server). For a capstone the empty packages are acceptable, but they should either be removed (with a note in CLAUDE.md) or have at least a placeholder docstring describing what would live there. Their existence in the module map without code may confuse reviewers.

### M13. `IngestionOrchestrator.process` is the only "orchestration" present, but lives in `src/ingestion/`
`src/ingestion/orchestration_hook.py` — wrong package per the architecture. This file should arguably live in `src/orchestration/`. The naming `orchestration_hook` is also unusual; either it's an orchestrator (move it) or it's a hook (rename to clarify what it hooks into).

### M14. `Annotator.add_note` reads-then-writes without optimistic concurrency
`src/intelligence/annotator.py:74-86` fetches the row, appends, and writes back the full annotations JSON. Two concurrent calls would race — the loser silently drops their note. Capstone scope is single-user so this is fine, but add a CHECK or row version column in a later migration, and document the limitation here.

### M15. `_value_match` in eval comparator returns string-equal-by-default if floats won't parse
`src/eval/harness/comparator.py:149-153`
```python
try:
    e_val = float(extracted.strip())
    g_val = float(expected.strip())
except ValueError:
    return extracted.strip() == expected.strip()
```
A GT value of `"<100"` and an extracted value of `"<100"` will string-match correctly, but `"<100"` vs `"<100 "` will not (already stripped). More subtly: `"10.0"` vs `"10"` will parse and then exact-match because integer path is taken on `expected="10"` (no `.`), which fails `10.0 != 10` ... wait, `10.0 == 10` is True in Python. So this case is fine. But `"10.0"` (with `.`) triggers the decimal-tolerance path, which is `abs(10.0 - 10) / abs(10) = 0` → True. OK. Real edge: `"1,234"` vs `"1234"` — float() fails on the comma, falls to string compare → mismatch. Document the assumption that comma-thousands separators must be stripped before reaching the comparator.

### M16. `taxonomy_editor.add_alias` does not check whether the alias collides with `_normalize_key`-collapsed forms
`src/normalization/taxonomy_editor.py:31-35` does a `strip().lower()` collision check. But `_normalize_key` in `index_builder.py:9-17` *also* strips parenthetical descriptors and collapses whitespace. So `add_alias("HbA1c", "Hemoglobin  A1c")` (double space) would pass the editor's check but fail the index builder's invariant later, raising `ValueError` at the next lookup. Apply `_normalize_key` consistently.

## Low Priority / Suggestions

### L1. `Gateway.__init__` does not allow passing a custom `EvalLogger`
`src/gateway/gateway.py:50` — `self._logger = EvalLogger()` is hardcoded. Other dependencies are injectable. Minor inconsistency; would matter only for tests.

### L2. Test files for `mcp_server/` and `orchestration/` are empty directories
`tests/mcp_server/__init__.py` and `tests/orchestration/__init__.py` exist but have no tests. Either delete the dirs or add a placeholder `def test_placeholder(): pass` so future contributors know tests are expected.

### L3. `ruff.toml` selects only `["E", "F", "W", "I", "N", "UP"]`
No `B` (bugbear), no `S` (security), no `RET`, no `SIM`. Adding `B` would have flagged the bare `except Exception: pass` pattern as B903 / B015 without needing noqa comments.

### L4. The `eval_logger.EvalLogger` uses `Path(__file__).parent.parent.parent / "eval_corpus" / "runs"` for the default path
Same pattern in `_DEFAULT_SHARED_DIR`, `_DEFAULT_TAXONOMY_PATH`, `_DEFAULT_PROMPTS_DIR`, `_DATA_DIR` — six different files compute the project root by counting `.parent` calls. Centralize as `src/_paths.py` (`PROJECT_ROOT = Path(__file__).parent.parent`) and import from there. Future move of a file breaks four `.parent.parent.parent.parent` chains otherwise.

### L5. `_RETRY_SLEEP: dict[int, float] = {0: 0.0, 1: 1.0, 2: 2.0}` is identical in `anthropic_adapter` and `textract_adapter`
Extract.

### L6. The Pydantic v2 `model_dump(mode="json")` calls in repositories are bypassing the strict-mode round-trip
`biomarker_repository.add()` dumps to JSON, sends to Supabase, gets back data, then `model_validate(data[0], strict=False)`. The asymmetry — strict outbound, loose inbound — works around the `str→UUID` and `str→date` issues but defeats `model_config = ConfigDict(strict=True)` (`models.py:22`). The CLAUDE.md rule was that strict=True is mandatory. Document the inbound exception explicitly (`gotchas.md` mentions it for F5 only).

### L7. `safety_preamble.md` and `banned_phrases.txt` are loaded once at Gateway init
Correct per Layer2/Layer3 design. But changing these files requires a Gateway restart. The cost is low (Gateway is initialized per-process). If iteration on prompt-engineering banned-phrase lists becomes frequent, consider hot-reload.

### L8. `_RETRY_SLEEP.get(attempt, 2.0**attempt)` fallback never executes when `max_retries=3`
`anthropic_adapter.py:103`. Dead fallback because `attempt < max_retries - 1` is False at `attempt=2`. Either delete the fallback or genuinely use it (by allowing `max_retries > 3`).

### L9. Unused exception path `OwnershipLeakError` in `__init__.py` exports
`OwnershipLeakError` is exported but raised only by Mode A. The error message is also identical to the immediately-following `_security_log.error` log entry. The caller treats it as a `ModeAVerificationError` (it inherits). Consider whether the dedicated subclass earns its weight or could be a flag on `ModeAVerificationError`.

### L10. The `Subtype` enum has `OTHER` but `_SUBTYPE_LABELS` defines it as `"document"`
`src/ingestion/user_messages.py:27`. The user-facing message becomes "This looks like a document — Vitalog currently supports lab reports." Awkward phrasing. Suggest mapping OTHER to "unrecognized document type" or similar.

### L11. `_should_skip` uses bare `pre.split()[-1]` without bounds-check
`src/gateway/numeric_parser.py:114` — the explicit `if pre.split()` guard does prevent the IndexError. Reads cleanly. No issue, but the double `.split()` call is wasteful — store in a local.

### L12. `ContextCard.disclaimer` is filled from the module-level `DISCLAIMER` constant, but `Summary.disclaimer` is set imperatively from a different module-level constant
Two places, same text *almost*. Compare `src/intelligence/context_cards.py:27-30` to `src/intelligence/summary_generator.py:20-24`. They differ slightly in wording. Either unify or document the deliberate divergence.

### L13. The `# Mark's patient profile` mentioned in `CLAUDE.md` Gotchas references `reference_data/mark_profile.json` but the loader path in `patient_profile.py:18` is `_MARK_PROFILE_PATH = _DATA_DIR / "mark_profile.json"` where `_DATA_DIR = Path(__file__).parent.parent.parent / "reference_data"`. That works. The CLAUDE.md says "do not load from Supabase unless task 18 (if-time) has landed" — confirm task 18 status before relying on the docs.

### L14. `eval/harness/reporter._git_sha` could return empty string silently
Line 138-139 — `(CalledProcessError, FileNotFoundError)` returns `""`. The empty value is then written to history.csv. Recommend logging when this falls through so an unrelated env breakage doesn't produce silently-rotten history rows.

### L15. `pyproject.toml` does not pin `python-dotenv` even though `tests/conftest.py` imports it
`from dotenv import load_dotenv` — relies on `dotenv` being a transitive dep. If a future dep removes it, all tests break with an import error before any test runs. Add `python-dotenv` to the dev group or remove the import.

### L16. `range_overlay._parse_range` uses regex but does not normalize a leading `~` or `+/-` qualifier
A guideline string `"~5-7"` would parse as `(None, None)`. Currently no curated range uses `~`, so this is safe. Add a comment or a sanity test.

## Module-by-Module Notes

**`src/gateway/`** — The chokepoint design is well-implemented. `gateway.py` is the most complex file but reads cleanly with the "guardrail seams" docstring. The retry logic in `_call_with_l3_retry` is the most thoughtful retry I've seen in this codebase — system prompt is amended with explicit failure context, which is *exactly* what should happen at F2/F3/F5 retry sites too (C3). The two adapters are correctly isolated. The numeric_parser has a lot of accumulated heuristics (date-of-month exclusion, English-verb unit filter) that work today but would benefit from a doctest block showing each case.

**`src/ingestion/`** — The 6-step validate pipeline + 3-band confidence model is the cleanest part of the codebase. The orchestration_hook.py belongs in src/orchestration/ (M13). Textract normalization is solid but has the known merged-cell limitation (M8). The classifier's PDF-text extraction has a brittle exception-handling shape (H7).

**`src/normalization/`** — Tiny, well-focused. The cache invalidation issue (H1) is the biggest concern. `unit_converter` uses `_units_equal` for case-fold comparison — documented as pragmatic. The duplicate detector logic is correct but the audit event_type naming is inconsistent (M3).

**`src/intelligence/`** — Largest concern is the boilerplate retry-twice pattern duplicated across observation, nlq, summary (C3). The `_attempt`/`_log_audit` shape is also copy-pasted across all three. Extract a `ProtectedLLMCall` base class or helper that owns:
- Two-attempt loop with second-attempt prompt augmentation
- Audit logging
- Safe-refusal fallback shape
This would shrink the modules by ~30% and prevent drift.

`range_overlay`, `retrieval`, `trend_engine` are the deterministic core and are well-tested. The context_cards module has a clean two-path (guideline JSON → taxonomy fallback) structure.

**`src/persistence/`** — Repository pattern is correctly implemented. The `Any` typing in models.py (C5) is the main issue. RLS policies in migration 001 are textbook. The asymmetric `strict=True` outbound / `strict=False` inbound (L6) is a known compromise that warrants explicit documentation.

**`src/eval/`** — Comparator/aggregator/runner/reporter are well-factored. The dry-run mode (GT self-comparison) is a particularly nice testing affordance. The reporter writes accuracy.json with `default=_serialise` which is fine but won't handle nested non-dataclass types if they appear later. The grader's reliance on a private function `_load_banned_phrases` (gotcha noted in `gotchas.md`) is fragile.

**`src/reference_data/`** — Tight and small. The lint.py invariant checker is excellent for catching curation drift. The `_REQUIRED_ENTRY_FIELDS` set is duplicated between `__init__.py` and `lint.py` — comment says they must stay in sync, but no test enforces it. Add `assert _REQUIRED_ENTRY_FIELDS == reference_data._REQUIRED_ENTRY_FIELDS` somewhere.

**`tests/`** — Strong coverage. Test organization mirrors src/. Conftests are minimal which is good. A few test files (`tests/intelligence/test_summary_end_to_end.py`, `test_summary_generator.py`, `test_summary_constraints.py`) split testing of one feature across three files — moderately confusing. No `test_observation_generator.py` analog with safe-refusal-path coverage was visible; verify.

## Positive Observations

1. **Architecture-as-code is real.** The CLAUDE.md module map is accurate; the docs aren't aspirational. Tests like `test_no_direct_anthropic_imports.py` enforce architectural rules at CI time.
2. **The AI Gateway chokepoint works.** The grep for `anthropic` outside `src/gateway/` returns zero hits in `src/`. Only the adapter and the gateway top-level import it.
3. **The Mode A vs Mode B distinction is principled.** Mode A is structured tool-use citations for the summary (highest-stakes output); Mode B is parse-and-match for prose. The split lives both in code and in `docs/Vitalog_architecture.md` §7.2.1. The verifier modules are pure deterministic with zero I/O — `verify(citations, patient_id, retrieval_set) -> None` and `verify(prose, retrieval_set) -> None` are textbook contracts.
4. **Layered guardrails are layered.** L1 (PHI redact + injection detect, fail-open with warning), L2 (preamble + few-shots, fail-soft if files missing), L3 (banned phrases + schema, fail-with-retry). Each layer has its own module, test file, and known limitations.
5. **Threshold constants are named.** `THRESHOLD_AUTO_ACCEPT`, `THRESHOLD_REJECT`, `THRESHOLD_FALLBACK`, `MODE_A_NUMERIC_TOLERANCE`, `MODE_B_NUMERIC_TOLERANCE`. No magic numbers in hot paths.
6. **Composite confidence uses `min()`.** The conservative-bias design (`composite_confidence.py:25`) is exactly right for health data. Documented inline.
7. **Pending-taxonomy guards.** F2 explicitly raises `ValueError` on `canonical_biomarker_id is None`. The gotchas.md catalogs precisely the kind of subtle invariant a new contributor would otherwise break.
8. **Storage policy is gated, not just labelled.** `storage_router.py` actually returns a `discard://<uuid>` URI for not_supported documents — the file is not just labelled discarded; it never leaves memory. Verified in code.
9. **Audit log hash chain (migration 002).** Provenance is taken seriously enough that the audit log is tamper-evident at the DB level, even though the application code never reads the hashes.
10. **The .githooks/pre-commit + native git hook flow.** Eliminates the entire class of "I forgot to run lint" PR drama. `make setup` activates it. Clear win.
11. **Tests run without `.env`.** The conftest gracefully loads `.env` if present but doesn't require it for unit tests. Integration tests are explicitly marked and skipped by default.
12. **The eval harness has a dry-run mode that exercises the full scaffold without LLM calls.** Engineering rigor.
