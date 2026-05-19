# G1 — MCP server + 6 tools wired

**Epic:** Top Layer
**Points:** 8
**Priority:** Critical
**Depends on:** D, E, F complete (specifically D1–D6, E1–E4, F1, F3, F5, F6, G2)
**Architecture refs:** §5.7; ADR-08; PRD v2 §Functional Requirements; demo channel

## User story

As Mark using Claude Desktop,
I want six MCP tools — upload_document, list_biomarkers, get_trend, query_records, prepare_summary, export_summary — exposed by a thin stdio MCP server,
So that I can do everything the capstone promises through Claude Desktop's natural language interface.

## Why this matters

P2 (channel-agnostic value layer) and ADR-08 (MCP-only for capstone) both converge here. The MCP server is the demo channel — without it, there is no demo. The architecture's discipline is that this layer is a THIN protocol adapter: zero business logic, zero persistence calls, zero LLM calls of its own.

## Acceptance criteria

1. **Given** the MCP server is registered in Claude Desktop's config (`claude_desktop_config.json`), **When** I open Claude Desktop, **Then** all 6 tools appear in the tool list with their descriptions.
2. **Given** the `upload_document(file)` tool, **When** invoked from Claude Desktop with a sample PDF, **Then** the document is processed end-to-end and the response includes a summary count ("9 results added, 1 pending taxonomy, 1 user review, 0 rejected").
3. **Given** the `list_biomarkers(patient_id, filter?)` tool, **When** invoked, **Then** the response includes a list of biomarkers Mark has data for, with latest value + collection_date + record_count.
4. **Given** the `get_trend(patient_id, biomarker_id)` tool, **When** invoked with `"hba1c"` for Mark, **Then** the response includes 9 points (post-H1) + target band + per-point provenance, rendered as chart-ready data.
5. **Given** the `query_records(patient_id, question)` tool, **When** invoked with "show me my diabetes markers", **Then** the response is the NLQ Handler's output.
6. **Given** the `prepare_summary(patient_id)` tool, **When** invoked, **Then** the response is the Summary Generator's structured output (no specialist or visit_type params — removed in F5 design).
7. **Given** the `export_summary(summary_id, format)` tool, **When** invoked with `format="pdf"`, **Then** the response includes a base64-encoded PDF or a Supabase Storage URL that Claude Desktop can present.
8. **Given** the contract, **When** I `grep "anthropic\|Anthropic\|Gateway\|Repository\|Supabase" src/mcp_server/`, **Then** the only matches are imports from `src.orchestration` — the MCP layer never touches services directly.

## Files to create / modify

- `src/mcp_server/__init__.py`
- `src/mcp_server/server.py` — stdio MCP server entry
- `src/mcp_server/tools/upload.py`
- `src/mcp_server/tools/list_biomarkers.py`
- `src/mcp_server/tools/get_trend.py`
- `src/mcp_server/tools/query.py`
- `src/mcp_server/tools/prepare_summary.py`
- `src/mcp_server/tools/export.py`
- `src/orchestration/__init__.py` — workflow coordinators (`upload_document_workflow`, `view_trend_workflow`, `query_workflow`, `generate_summary_workflow`, `export_workflow`)
- `scripts/run_mcp_server.py` — entry point script for Claude Desktop config
- `tests/mcp_server/test_tools_smoke.py` — invokes each tool via the MCP test harness

## Implementation notes

- Use the Anthropic Python MCP SDK (`mcp` dep from A1). Transport: `stdio` for local Claude Desktop, `sse` for remote deployment — controlled by `MCP_TRANSPORT` env var.
- `upload_document` accepts `file_content_base64 + filename` (not `file_path`). User attaches PDF in Claude chat → Claude encodes it → calls the tool. Works for both local and remote deployment with no separate upload UI.
- Each tool is a thin wrapper: validate inputs, call the appropriate Orchestration workflow, format the response. NO logic beyond that. NO calls to Anthropic from this layer.
- Orchestration layer (architecture §5.6) holds the workflow coordinators. The MCP tool is `(input) → (workflow call) → (response)`. The workflow is `(workflow) → (compose service calls)`. Strict separation.
- For PDF export, the MCP tool returns the bytes inline (base64) so Claude Desktop can present a downloadable file. Don't try to render the PDF inline as text.
- Tool descriptions in the MCP registration must be precise — Claude Desktop uses these to decide when to call them. Document each tool with a one-line description + one parameter description per arg.
- For capstone, all 6 tools operate on `patient_id` = `MARK_PATIENT_ID` (hardcoded UUID from G2). The MCP tool signatures accept patient_id but capstone validates it against the hardcoded value in `_guard.py`.

## Verification

- `python scripts/run_mcp_server.py` — server starts without errors
- Register the server in `claude_desktop_config.json`, restart Claude Desktop, confirm all 6 tools appear
- End-to-end via Claude Desktop: ask "upload this lab report" with a synthetic PDF; ask "show me my HbA1c trend"; ask "prepare a cardiology first-visit summary"; ask "export the summary as PDF"
- `pytest tests/mcp_server/test_tools_smoke.py -q`
- The architectural-layering test: `grep -E "anthropic|supabase" src/mcp_server/ -r` returns zero matches outside imports from `src.orchestration` / `src.persistence.models` (Pydantic models for typing are okay).

## INVEST check

- [x] Independent — needs every other epic's contracts but no other story for the MCP layer itself
- [x] Negotiable — exact tool signatures negotiable within architecture §5.7
- [x] Valuable — the demo channel
- [x] Estimable — well-bounded SDK integration
- [x] Small — 8 pts (at the cap; do NOT split further — splitting MCP tools individually creates orchestration churn)
- [x] Testable — smoke tests + manual demo run

## Deferred (explicitly out of this story)

- Web UI top layer — v1
- WhatsApp / SMS top layer — v1+
- Per-tool rate limiting / quotas — v1
- Authentication beyond the hardcoded Mark UUID — v1

## Notes / changelog

### Implementation (2026-05-18)

**Files created:**
- `src/orchestration/container.py` — `ServiceContainer` dataclass + `build_container()` (lru_cache singleton)
- `src/orchestration/workflows.py` — 5 workflow functions + `UploadResult` / `GenerateSummaryResult` schemas; full normalization+persistence pipeline wired in `_normalize_and_persist()`
- `src/orchestration/__init__.py` — replaced placeholder; re-exports all public symbols
- `src/mcp_server/server.py` — FastMCP instance, 6 `@mcp.tool` registrations, lazy container singleton
- `src/mcp_server/tools/__init__.py`, `upload.py`, `list_biomarkers.py`, `get_trend.py`, `query.py`, `prepare_summary.py`, `export.py`
- `src/mcp_server/tools/_guard.py` — `validate_patient_id()` capstone patient-ID guard
- `scripts/run_mcp_server.py` — entry point; stdio (default) or SSE via `MCP_TRANSPORT` env var
- `tests/mcp_server/test_tools_smoke.py` — 18 smoke tests (all pass)

**Key design decisions:**
- `upload_document` uses `file_content_base64 + filename` (not `file_path`) so the flow works for remote deployment: user attaches PDF in Claude → Claude encodes it → tool decodes and runs pipeline. No separate upload UI.
- Transport switching via `MCP_TRANSPORT` env var (`stdio` for local, `sse` for deployed).
- Patient-ID guard lives in `src/mcp_server/tools/_guard.py` — capstone auth concern, not orchestration business logic.
- `VerifiedBy` type annotation required on `verified_by` local variable to satisfy mypy strict mode.

**Layering check passed:** `grep -rE "anthropic|supabase|Gateway|Repository" src/mcp_server/` → zero matches outside `src.orchestration` imports (AC8 ✅).
