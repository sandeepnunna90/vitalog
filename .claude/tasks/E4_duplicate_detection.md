# E4 — Duplicate detection

**Epic:** Normalization
**Points:** 3
**Priority:** High
**Depends on:** E1, E3
**Architecture refs:** §5.2 (Duplicate Detection section); PRD v2 Scenario 3

## User story

As Mark uploading the same Quest report twice by accident,
I want Vitalog to detect the duplicate, store both records, and notify me,
So that my trend isn't double-counting a single lab visit, but no data is silently discarded.

## Why this matters

The architecture choice "Both records stored if ambiguous; user/admin notified" matters: data is never auto-deleted. PRD v2 Scenario 3 makes this explicit. Capturing duplicates protects against both user error and data-pipeline replay scenarios.

## Acceptance criteria

1. **Given** an incoming biomarker record with `canonical_id="hba1c"`, `collection_date="2026-03-12"`, `canonical_value=6.8`, **When** a record with the same `canonical_id` + `collection_date` exists for the same patient AND its `canonical_value` is within 0.5% tolerance, **Then** the new record is stored AND a `DuplicateDetected` notification is added to the upload-response.
2. **Given** two records with same canonical_id + date but values differing by more than 0.5%, **When** dedup runs, **Then** both records are stored, NO duplicate flag is set, and `value_conflict=true` is logged in the audit trail (different scenario — measurement disagreement, not duplicate upload).
3. **Given** a record whose date is one day off from an existing record, **When** dedup runs, **Then** they are NOT treated as duplicates (date match is exact, not fuzzy).
4. **Given** the duplicate detection, **When** the response surfaces to the user, **Then** the message names the prior document by `lab_source` + `collection_date` so Mark can verify (e.g., "This looks like a duplicate of your March 12 Quest report").
5. **Given** the contract, **When** records are stored, **Then** NEITHER is auto-deleted — Mark must manually deduplicate via the review queue (capstone has no user-facing dedup resolution; v1 will).
6. **Given** the audit log, **When** a duplicate is detected, **Then** an event of type `duplicate_detected` is recorded with both record_ids.

## Files to create / modify

- `src/normalization/duplicate_detector.py`
- `src/persistence/biomarker_repository.py` — extend with `find_potential_duplicates(patient_id, canonical_id, collection_date)`
- `tests/normalization/test_duplicate_detector.py`

## Implementation notes

- Duplicate key: `(patient_id, canonical_id, exact collection_date, canonical_value within ±0.5%)`. All four must match for "duplicate"; partial match is "value conflict".
- The 0.5% tolerance matches Mode B's numeric tolerance (`MODE_B_NUMERIC_TOLERANCE`). Define once, reuse.
- Detection runs AFTER unit conversion (E3) so we're comparing apples-to-apples in canonical units.
- For records that lack a collection_date (rare; means the structurer couldn't extract one), skip dedup and flag the record for user review instead.
- The notification message is added to the orchestration response, not stored in the biomarker record. The audit log captures the detection event for analytics.
- Capstone scope is "detect + notify". Resolution (user picks which to keep, or merges) is v1.

## Verification

- `pytest tests/normalization/test_duplicate_detector.py -q` covering: exact duplicate, value-conflict (different values same date), date-off-by-one, missing-date, multi-patient isolation
- Manual: upload the same synthetic doc twice via the upload flow, observe duplicate notification

## INVEST check

- [x] Independent — E1 + E3 required
- [x] Negotiable — exact tolerance flexible (reuse `MODE_B_NUMERIC_TOLERANCE`)
- [x] Valuable — gates user trust + data quality
- [x] Estimable — well-bounded
- [x] Small — 3 pts
- [x] Testable — extensive AC coverage

## Deferred (explicitly out of this story)

- User-facing dedup resolution UI — v1
- Fuzzy date matching (e.g., "same week" — risky, defer) — likely never
- Auto-merge with audit trail — v2

## Notes / changelog

### Implementation (2026-05-17)

**Files created:**
- `src/normalization/constants.py` — `MODE_B_NUMERIC_TOLERANCE = 0.005` as shared constant; decouples future Mode B (B5) from the detector module
- `src/normalization/duplicate_detector.py` — `DuplicateCheckResult` (Pydantic, Literal status) + `DuplicateDetector.check()`; `audit_repo` required injection; `_build_notification()` private helper
- `tests/normalization/test_duplicate_detector.py` — 16 unit tests (14 original + 2 from PR review fixes)

**Files modified:**
- `src/persistence/biomarker_repository.py` — added `find_potential_duplicates(patient_id, canonical_id, collection_date)`
- `src/normalization/__init__.py` — exports `DuplicateDetector`, `DuplicateCheckResult`, `MODE_B_NUMERIC_TOLERANCE`

**Key design decisions:**
- Tolerance constant in `constants.py` (not `duplicate_detector.py`) so Mode B can import it without coupling to the detector
- Literal status string (`"duplicate"/"value_conflict"/"no_match"/"skipped_no_date"`) rather than boolean flags — tagged union with no impossible states
- `audit_repo` required (not optional) — consistent with codebase pattern; optional would silently drop events in production
- `check()` called after storage so both `record_id`s are available for the AC6 audit event
- Prior records with `canonical_value=None` are skipped (can't compare)
- Zero-value guard: `if ref == 0.0: within_tolerance = canonical_value == 0.0` prevents `ZeroDivisionError`

**PR review fixes (PR #18):**
- Fixed first-match-only bug: original `else: return` inside loop short-circuited on first value_conflict, missing any exact duplicate later in the list. Restructured to accumulate `conflict_prior` and continue iterating; duplicate always takes priority.
- Added `dedup_skipped_no_date` audit event when `collection_date is None` — surfaces skipped dedup in analytics
- Added 2 new tests: `test_duplicate_wins_over_earlier_conflict` (covers loop fix) and `test_audit_event_on_skipped_no_date`; added negative assertion to `test_no_existing_records_returns_no_match`
- Added comment on `%-d` strftime portability
