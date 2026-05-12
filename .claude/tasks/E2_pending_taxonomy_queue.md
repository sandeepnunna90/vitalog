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

_(append after work is done)_
