# E1 — Tier 1 LOINC-aware alias lookup

**Epic:** Normalization
**Points:** 3
**Priority:** Critical
**Depends on:** A2, A3
**Architecture refs:** §5.2 (Tier 1); ADR-03; PRD v2 Normalization rows

## User story

As Mark uploading lab reports from Quest and LabCorp,
I want the same biomarker (HbA1c, Hemoglobin A1c, A1C, glycohemoglobin) to resolve to the same canonical ID regardless of which lab's spelling appears,
So that my HbA1c trend pulls together data from every lab on one chart.

## Why this matters

Tier 1 is the workhorse of normalization. Without it, the demo's headline chart — 9 HbA1c points across 3 labs — falls apart because each lab's spelling creates a different "biomarker". P4 (determinism where possible) puts this at the top of the must-be-deterministic list.

## Acceptance criteria

1. **Given** the 30-entry taxonomy seed from A2, **When** I look up the alias `"HbA1c"`, **Then** I get `vitalog_id = "hba1c"`.
2. **Given** the same alias index, **When** I look up `"Hemoglobin A1c"`, `"A1C"`, `"glycohemoglobin"`, **Then** all four resolve to `"hba1c"`.
3. **Given** a raw name not in any alias list, **When** I look up via Tier 1, **Then** I get `None` and the caller routes to Tier 4 (E2 pending queue).
4. **Given** case variants (`"HBA1C"`, `"hba1c"`, `"HbA1c"`), **When** I look up, **Then** all resolve to the same `vitalog_id`.
5. **Given** the alias index, **When** I `from src.normalization.tier1 import lookup`, **Then** the function is the only public entry point — no exposed dict, no leaks of the underlying data structure.
6. **Given** the contract, **When** I time the lookup, **Then** it is O(1) (in-memory hash index built once at startup).

## Files to create / modify

- `src/normalization/__init__.py`
- `src/normalization/tier1.py` — alias index + `lookup(raw_name) -> Optional[str]`
- `src/normalization/index_builder.py` — builds the alias → vitalog_id map from `biomarker_taxonomy.json`
- `tests/normalization/test_tier1.py`

## Implementation notes

- Alias matching is case-insensitive and whitespace-collapsed (`"  Hemoglobin   A1c  "` → matches `"Hemoglobin A1c"`).
- Punctuation handling: strip parenthetical descriptors (`"HbA1c (glycated hemoglobin)"` → matches `"HbA1c"`).
- The index is built from `reference_data/biomarker_taxonomy.json` at startup; rebuilt only when the file changes.
- If two taxonomy entries share an alias, the index builder raises at load time — this is a curation bug, never a runtime issue.
- The lookup function does NOT fall back to fuzzy match (that's Tier 2, deferred to v1). Capstone behavior is strict: hit or miss.
- Performance is irrelevant in absolute terms (30 entries) but the contract (O(1), pure-deterministic, no LLM) matters for the v1 → v2 grow path.

## Verification

- `pytest tests/normalization/test_tier1.py -q` covering all canonical names from the 30-entry seed + edge cases (case, whitespace, punctuation)
- Manual: load the index, count entries, spot-check known multi-alias cases (HbA1c, LDL-C)

## INVEST check

- [x] Independent — only A2 + A3 required
- [x] Negotiable — exact normalization rules flexible
- [x] Valuable — gates the entire trends story
- [x] Estimable — well-bounded
- [x] Small — 3 pts
- [x] Testable — exhaustive coverage of the 30 entries

## Deferred (explicitly out of this story)

- Tier 2 fuzzy match (string + embedding similarity) — v1
- Tier 3 live LOINC lookup — v1
- Confidence-based routing across tiers — v1

## Notes / changelog

### Implementation (2026-05-16)

**Files created:**
- `src/normalization/index_builder.py` — `_normalize_key()` strips parentheticals, collapses whitespace, lowercases; `build_index()` raises `ValueError` on duplicate alias across entries (fail-fast for curation bugs)
- `src/normalization/tier1.py` — `lookup(raw_name) -> str | None` backed by `lru_cache(maxsize=1)` index; only public entry point
- `src/normalization/__init__.py` — re-exports `lookup`
- `tests/normalization/test_tier1.py` — 303 tests (all 30 canonical names + all aliases parametrized, case folding, whitespace, parentheticals, unknown→None, duplicate detection, stability)

**Key design decisions:**
- Built own enhanced index from `load_taxonomy()` rather than delegating to `reference_data._get_alias_index()` — that one lacks whitespace collapsing and parenthetical stripping
- `_normalize_key` uses `re.sub(r"\s*\(.*?\)", "", raw)` which correctly strips multiple parenthetical groups
- `build_index` raises at index construction time (startup), not at lookup time — curation bugs fail fast

**PR review fixes:**
- Added module-level `_TAXONOMY = load_taxonomy()` in tests to replace 5 repeated `load_taxonomy()` calls in `@pytest.mark.parametrize` decorators
- Replaced `test_index_is_cached` (accessed private `_index` internals) with `test_repeated_lookups_are_stable` (tests observable contract)
- Removed `_index` import from test file — no longer needed
