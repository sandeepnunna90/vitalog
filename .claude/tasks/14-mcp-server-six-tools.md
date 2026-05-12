# Task 14 — MCP server: six tools

## Context

Per architecture §5.7, the MCP server exposes six tools that Claude Desktop can call: `upload_document`, `list_biomarkers`, `get_trend`, `query_records`, `prepare_summary`, `export_summary`. Each tool is thin — input validation + service delegation. This is the surface that the demo runs through; everything before this was making it possible.

## Dependencies

- Tasks 04–07 (ingestion pipeline)
- Task 08 (persistence)
- Task 09 (normalization)
- Task 11 (trend engine)
- Task 12 (observation generator — for context cards)
- Task 13 (summary generator + export)

## In scope

`src/mcp_server/`:

- `server.py` — Anthropic Python MCP SDK stdio server.
- `tools/upload_document.py` — input: file path or bytes; runs `Pipeline.ingest` → `Normalizer.normalize` → persist. Returns counts: `{accepted: N, pending_user: M, pending_taxonomy: K, rejected: J}`.
- `tools/list_biomarkers.py` — input: patient_id; returns latest record per canonical biomarker with units + collection_date.
- `tools/get_trend.py` — input: patient_id, canonical_id; returns `TrendSeries`.
- `tools/query_records.py` — capstone stub: returns "Natural-language query is not in capstone scope; use list_biomarkers or get_trend instead." (Wires to NLQ Handler if task 17 done.)
- `tools/prepare_summary.py` — input: patient_id, specialist, visit_type; runs `SummaryGenerator.generate`. Returns `SummaryDocument` as JSON.
- `tools/export_summary.py` — input: summary_id, format; returns file path or base64 bytes.
- `README.md` snippet: Claude Desktop config (paths, env vars).
- Stdio transport per MCP standard.

Each tool declares its input/output schema using Pydantic and registers itself with the MCP server. All audit events flow into the audit log via the persistence layer.

## Out of scope (deferred)

- HTTP / SSE transports (capstone uses stdio only).
- Tool-level rate limiting (v1).
- Streaming responses for long generations (v1).

## Files to create

- `src/mcp_server/__init__.py`
- `src/mcp_server/server.py`
- `src/mcp_server/tools/__init__.py`
- `src/mcp_server/tools/upload_document.py`
- `src/mcp_server/tools/list_biomarkers.py`
- `src/mcp_server/tools/get_trend.py`
- `src/mcp_server/tools/query_records.py`
- `src/mcp_server/tools/prepare_summary.py`
- `src/mcp_server/tools/export_summary.py`
- `tests/mcp_server/test_*.py` (one per tool; mocked services)
- Update `README.md` with the Claude Desktop config snippet.

## Architecture references

- `docs/Vitalog_architecture.md` §5.7 — MCP server + tool surface
- `docs/Vitalog_architecture.md` ADR-08 — MCP-only demo for capstone
- `docs/Vitalog_PRD_v2.md` §GTM Week 3 "MCP server"

## Step-by-step

1. Read Anthropic Python MCP SDK docs / examples; scaffold `server.py`.
2. Implement each tool as a thin function with Pydantic-validated input/output.
3. Wire shared services (Pipeline, Normalizer, repositories, generators) as module-level singletons.
4. Stdio loop in `server.py`.
5. Tests: each tool tested with mocked services.
6. Manual: run `python -m src.mcp_server.server` in stdio mode; configure Claude Desktop to point at it; invoke each tool from a Claude conversation.

## Acceptance criteria

- [ ] All 6 tools register and are discoverable by Claude Desktop.
- [ ] Each tool returns Pydantic-validated output.
- [ ] `upload_document` end-to-end through ingestion + normalization + persistence works on a hero PDF.
- [ ] `get_trend mark vitalog:hba1c` returns 9 points.
- [ ] `prepare_summary mark cardiology first_visit` returns a Mode-A-verified summary.
- [ ] `export_summary <id> pdf` writes a PDF file path.
- [ ] `query_records` returns the not-in-capstone stub message.
- [ ] Audit events generated for every tool call.

## Verification

- `pytest tests/mcp_server -q`
- Manual Claude Desktop session: upload → list → trend → summary → export → success.
- Check audit log: one row per tool call, payload sanitized.
