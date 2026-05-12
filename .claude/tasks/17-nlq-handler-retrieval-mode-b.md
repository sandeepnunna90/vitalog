# Task 17 — NLQ Handler + retrieval + Mode B *(if-time)*

## Context

**If-time only.** Pick up only if you finish task 09 by end of Day 5. The Demo Slice in PRD v2 does not require NLQ; roadmap §4 exit criterion #1 does not require NLQ. But NLQ is in roadmap §4 in-scope, in PRD v2's Functional Requirements, and powers Scenario 4. Adding it makes the demo more impressive.

## Dependencies

- Task 09 (normalized records to retrieve over)
- Task 11 (trend engine — retrieval shares logic)
- Task 12 (Layer 3 + Mode B — reused)

## In scope

`src/intelligence/nlq_handler.py`:

- `NLQHandler.answer(patient_id, query) -> NLQResponse(text, citations, used_records)`.
- Retrieval-first per architecture §5.4.3:
  - Step 1: deterministic retrieval — parse query for biomarker hints (against taxonomy aliases), date hints, condition hints; pull matching records.
  - Step 2: if retrieval empty → graceful fallback message ("We don't have any X results yet.").
  - Step 3: if retrieval has results → Gateway call with `prompts/nlq/v1.md`, passing only the retrieved records.
- Mode B verification reused from task 12.
- Hard constraints in prompt: answer only from provided records; never use general medical knowledge alone; if data missing, say so.

Update `src/mcp_server/tools/query_records.py` (from task 14): replace the not-in-capstone stub with a call to `NLQHandler`.

## Out of scope (deferred)

- RAG over unstructured documents (visit notes) — v2.
- Cross-document reasoning over the full record — v2.
- Multi-turn NLQ — v1.

## Files to create

- `src/intelligence/nlq_handler.py`
- `prompts/nlq/v1.md`
- Update `src/mcp_server/tools/query_records.py`
- `tests/intelligence/test_nlq_handler.py`

## Architecture references

- `docs/Vitalog_architecture.md` §5.4.3 — NLQ Handler
- `docs/Vitalog_architecture.md` §7.2.1 — Mode B
- `docs/Vitalog_PRD_v2.md` §Functional Requirements "Trend View → Natural language query"
- `docs/Vitalog_PRD_v2.md` §Prompt Requirements "Query handler"

## Step-by-step

1. Implement deterministic retrieval — biomarker alias extraction from query string + record filter.
2. Write `prompts/nlq/v1.md` with strict "answer only from provided records" + Mode B-aware output.
3. Implement `NLQHandler.answer` orchestration.
4. Wire into MCP tool.
5. Test: "show me my diabetes markers" returns HbA1c + fasting glucose grouped trend.
6. Test: query for an unrecorded biomarker returns graceful fallback.

## Acceptance criteria

- [ ] "Show me my diabetes markers" returns HbA1c + fasting glucose with cited values.
- [ ] Query for unrecorded biomarker returns graceful fallback (not a hallucination).
- [ ] Mode B verification active; hallucinated numerics rejected.
- [ ] No banned phrases in output.
- [ ] MCP `query_records` no longer returns the stub message.

## Verification

- `pytest tests/intelligence/test_nlq_handler.py -q`
- Via Claude Desktop: `query_records mark "show me my diabetes markers"` returns valid grouped result.
- Via Claude Desktop: `query_records mark "what's my creatine kinase?"` returns graceful fallback.
