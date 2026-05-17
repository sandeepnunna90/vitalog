# E2 — Tier 4 pending taxonomy queue + admin CLI

**Epic:** Normalization
**Points:** 5
**Priority:** High
**Depends on:** E1, A3
**Architecture refs:** §5.2 (Tier 4); PRD v2 GTM pre-demo

## User story

As the founder running Vitalog,
I want every unrecognized biomarker to be staged in a pending queue with raw name and candidate LOINC codes, plus a CLI to resolve them,
So that I can clear the queue before the demo (architecture §12 OQ5) without rewriting code, and so v1 can graduate this into a user-facing flow.

## Why this matters

Tier 4 is the safety valve for capstone — when the 30-entry seed inevitably misses something, the record doesn't get dropped silently and it doesn't get auto-merged into the wrong canonical entry. Resolving the queue manually before demo is a hard capstone exit criterion (PRD v2 Success Criteria).

## Acceptance criteria

1. **Given** a biomarker candidate with no Tier 1 alias match, **When** Normalization processes it, **Then** a row is inserted into `pending_taxonomy_entry` with `raw_name`, `raw_unit`, `document_id`, `candidate_loinc_codes` (empty list for capstone), `similarity_to_existing` (empty for capstone), `status="pending"`.
2. **Given** a biomarker record linked to a pending entry, **When** I read the record, **Then** `verified_by = "pending_user"` and the record is NOT visible in trends until the pending entry is resolved.
3. **Given** the admin CLI, **When** I run `python scripts/resolve_pending.py list`, **Then** I see all pending entries with raw_name, document_id, count_of_linked_records.
4. **Given** the admin CLI, **When** I run `python scripts/resolve_pending.py confirm <pending_id> --canonical <vitalog_id>`, **Then** the pending entry is marked `confirmed`, all linked records' `canonical_biomarker_id` is set, `verified_by` becomes `"admin"`, and the taxonomy entry's alias list is updated (file-level edit to `biomarker_taxonomy.json`).
5. **Given** the admin CLI, **When** I run `python scripts/resolve_pending.py reject <pending_id>`, **Then** the entry is marked `rejected` and linked records remain non-visible.
6. **Given** the demo prerequisite, **When** the queue is empty (status=pending count = 0), **Then** `make pre-demo-check` reports green.

## Files to create / modify

- `src/normalization/pending_queue.py`
- `src/persistence/taxonomy_repository.py` — extend with `add_pending()`, `list_pending()`, `confirm_pending()`, `reject_pending()`
- `scripts/resolve_pending.py` — admin CLI
- `Makefile` — add `pre-demo-check` target
- `tests/normalization/test_pending_queue.py`
- `tests/scripts/test_resolve_pending_cli.py`

## Implementation notes

- For capstone, `candidate_loinc_codes` and `similarity_to_existing` are empty — Tier 2 and Tier 3 (which would populate them) are deferred to v1. The schema fields exist so the v1 grow path is additive.
- "Confirm" updates BOTH the database (linked records) AND the on-disk taxonomy file (alias list). This is the only path that legitimately edits `biomarker_taxonomy.json` after initial seed — make it a deliberate, audited operation (writes go through `TaxonomyEditor` which validates the resulting file against the schema before committing).
- After a `confirm` operation, Tier 1's in-memory index is rebuilt (the file is the source of truth, the index is a cache).
- The admin CLI is founder-only for capstone (PRD v2 §Functional Requirements row "Pending taxonomy queue"). No user-facing UI.
- `make pre-demo-check` runs a sequence: (1) queue empty, (2) adversarial suite passes, (3) accuracy harness passes thresholds, (4) end-to-end smoke test passes. This is the gate before demo.

## Verification

- `pytest tests/normalization/test_pending_queue.py -q`
- `pytest tests/scripts/test_resolve_pending_cli.py -q`
- Manual: ingest a synthetic doc with a fake biomarker, run the CLI to confirm/reject, observe taxonomy edits
- `make pre-demo-check` — works after demo prep completes

## INVEST check

- [x] Independent — E1 + A3 required
- [x] Negotiable — exact CLI shape flexible
- [x] Valuable — gates demo (hard exit criterion)
- [x] Estimable — well-bounded
- [x] Small — 5 pts
- [x] Testable — CLI behavior covered

## Deferred (explicitly out of this story)

- User-facing taxonomy review prompts — v1
- Confidence-based routing (auto-link high-confidence matches) — v1
- Auto-promote logic (N confirmations → canonical) — v2
- Admin dashboard UI — v2

## Notes / changelog

### Implementation (2026-05-16)

**Files created:**
- `src/normalization/pending_queue.py` — `PendingQueue.enqueue(raw_name, document_id, raw_unit)` thin wrapper around `TaxonomyRepository.add_pending()`; `candidate_loinc_codes` and `similarity_to_existing` intentionally empty for capstone
- `src/normalization/taxonomy_editor.py` — `add_alias(vitalog_id, alias, taxonomy_path)` is the only legitimate path to edit `biomarker_taxonomy.json`; validates no duplicate alias or canonical name collision, appends alias, writes file with `ensure_ascii=False`, calls `_index.cache_clear()` to rebuild Tier 1 index
- `scripts/resolve_pending.py` — admin CLI with three subcommands: `list` (prints table of pending entries), `confirm <id> --canonical <vid>` (add alias + bulk-update biomarker records + mark entry confirmed), `reject <id>` (mark entry rejected); uses `SUPABASE_SERVICE_ROLE_KEY` to bypass RLS
- `tests/normalization/test_pending_queue.py` — 5 unit tests covering `enqueue()` contract (raw_name, document_id, raw_unit passthrough, empty loinc/similarity, status=pending)
- `tests/scripts/test_resolve_pending_cli.py` — 12 unit tests covering `cmd_list`, `cmd_confirm`, `cmd_reject`; all Supabase and file I/O mocked

**Files modified:**
- `src/persistence/biomarker_repository.py` — added `resolve_pending_records(pending_taxonomy_id, canonical_biomarker_id) -> int`; bulk-updates canonical and `verified_by='admin'` for all records linked to a pending entry; returns count updated
- `Makefile` — added `pre-demo-check` target: (1) query Supabase for pending=0, (2) run unit tests; skips C3/C5 accuracy gates (deferred)

**Key design decisions:**
- Operation ordering in `cmd_confirm`: `add_alias` runs before `resolve_pending_records` so an invalid `--canonical` id fails fast (ValueError) before any DB writes, avoiding FK violations mid-operation
- `TaxonomyEditor` clears Tier 1's `lru_cache` after every write so the in-memory alias index stays consistent with the file; cache is rebuilt lazily on the next `lookup()` call
- CLI intentionally exits with `SystemExit(1)` (via `sys.exit`) when a pending_id is not found — fail-loud rather than silently continue
- Duplicate alias during `confirm` is tolerated with a warning (not a hard error) since the alias may already exist legitimately (e.g., confirming a second pending entry for the same raw_name)

**PR review fixes:**
- Swapped operation order in `cmd_confirm`: moved `add_alias` block before `resolve_pending_records` to ensure taxonomy validation precedes any DB mutation
- Fixed ruff N806 (variable names that shadowed class names), F841 (unused mock variables), F821 (undefined mock_index reference)

**PR:** #16 (merged)
