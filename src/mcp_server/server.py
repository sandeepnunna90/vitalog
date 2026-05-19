"""Vitalog MCP server — exposes 6 tools to Claude Desktop / Claude.ai via FastMCP.

Transport is selected by MCP_TRANSPORT env var:
  stdio (default) — for local Claude Desktop
  sse             — for remote deployment (Railway, Fly.io, etc.)

Patient identity is resolved from VITALOG_PATIENT_ID env var inside each tool
module. It is not exposed as a parameter — tools work without the caller
supplying any identity information.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from src.mcp_server.tools import export as _export
from src.mcp_server.tools import get_trend as _get_trend
from src.mcp_server.tools import list_biomarkers as _list_biomarkers
from src.mcp_server.tools import prepare_summary as _prepare_summary
from src.mcp_server.tools import query as _query
from src.mcp_server.tools import upload as _upload
from src.orchestration import ServiceContainer, build_container

mcp: FastMCP = FastMCP("Vitalog")


def _get_container() -> ServiceContainer:
    return build_container()


# ── Tool registrations ────────────────────────────────────────────────────────


@mcp.tool(
    description=(
        "Upload a lab report to Vitalog. "
        "Pass filename (e.g. 'Lab-Report-2019.pdf') to upload a specific file from ~/Downloads. "
        "Call with no arguments to auto-pick the newest PDF in ~/Downloads. "
        "Returns a summary of extracted biomarker records."
    )
)
def upload_document(filename: str | None = None) -> str:
    return _upload.run(None, filename, _get_container())


@mcp.tool(
    description=(
        "List all biomarkers the patient has data for, with the latest value and date. "
        "Optionally filter by a substring of the biomarker ID "
        "(e.g. 'glucose' matches fasting_glucose)."
    )
)
def list_biomarkers(filter: str | None = None) -> str:
    return _list_biomarkers.run(_get_container(), filter=filter)


@mcp.tool(
    description=(
        "Return the longitudinal trend for a single biomarker — all recorded values over time "
        "plus published guideline target bands. "
        "Use canonical biomarker IDs such as 'hba1c', 'fasting_glucose', 'ldl_cholesterol'."
    )
)
def get_trend(biomarker_id: str) -> str:
    return _get_trend.run(biomarker_id, _get_container())


@mcp.tool(
    description=(
        "Answer a natural-language question about the patient's stored health records. "
        "Examples: 'Show me my diabetes markers', 'What was my last HbA1c?', "
        "'Do I have any thyroid results?'"
    )
)
def query_records(question: str) -> str:
    return _query.run(question, _get_container())


@mcp.tool(
    description=(
        "Generate a one-page appointment summary from all stored biomarker records. "
        "Returns the full summary text plus a summary_id for PDF/markdown/JSON export. "
        "All numeric values are citation-verified against stored records."
    )
)
def prepare_summary() -> str:
    return _prepare_summary.run(_get_container())


@mcp.tool(
    description=(
        "Export a previously generated summary as PDF, markdown, or JSON. "
        "Use the summary_id returned by prepare_summary. "
        "PDF is returned as base64-encoded content; markdown and JSON are returned as text."
    )
)
def export_summary(summary_id: str, format: str) -> str:
    return _export.run(summary_id, format, _get_container())
