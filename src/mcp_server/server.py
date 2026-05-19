"""Vitalog MCP server — exposes 6 tools to Claude Desktop / Claude.ai via FastMCP.

This module is a thin protocol adapter: each tool delegates immediately to a
tool module, which calls the orchestration layer. No business logic here.

Transport is selected by MCP_TRANSPORT env var:
  stdio (default) — for local Claude Desktop
  sse             — for remote deployment (Railway, Fly.io, etc.)
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
    # build_container is @lru_cache(maxsize=1) — thread-safe, built once per process.
    return build_container()


# ── Tool registrations ────────────────────────────────────────────────────────


@mcp.tool(
    description=(
        "Upload a lab report (PDF or image) to Vitalog. "
        "Provide either file_path (absolute path on the local filesystem) or "
        "file_content_base64 (base64-encoded file content). "
        "patient_id is optional — omit it to use the VITALOG_PATIENT_ID env var. "
        "Returns a summary of extracted biomarker records "
        "(auto-accepted, pending review, pending taxonomy, rejected)."
    )
)
def upload_document(
    filename: str,
    patient_id: str | None = None,
    file_path: str | None = None,
    file_content_base64: str | None = None,
) -> str:
    return _upload.run(
        file_content_base64, filename, patient_id, _get_container(), file_path=file_path
    )


@mcp.tool(
    description=(
        "List all biomarkers the patient has data for, with the latest value and date. "
        "Optionally filter by a substring of the biomarker ID "
        "(e.g. 'glucose' matches fasting_glucose)."
    )
)
def list_biomarkers(patient_id: str | None = None, filter: str | None = None) -> str:
    return _list_biomarkers.run(patient_id, _get_container(), filter=filter)


@mcp.tool(
    description=(
        "Return the longitudinal trend for a single biomarker — all recorded values over time "
        "plus published guideline target bands. "
        "Use canonical biomarker IDs such as 'hba1c', 'fasting_glucose', 'ldl_cholesterol'."
    )
)
def get_trend(biomarker_id: str, patient_id: str | None = None) -> str:
    return _get_trend.run(patient_id, biomarker_id, _get_container())


@mcp.tool(
    description=(
        "Answer a natural-language question about the patient's stored health records. "
        "Examples: 'Show me my diabetes markers', 'What was my last HbA1c?', "
        "'Do I have any thyroid results?'"
    )
)
def query_records(question: str, patient_id: str | None = None) -> str:
    return _query.run(patient_id, question, _get_container())


@mcp.tool(
    description=(
        "Generate a one-page appointment summary from all stored biomarker records. "
        "Returns the full summary text plus a summary_id for PDF/markdown/JSON export. "
        "All numeric values are citation-verified against stored records."
    )
)
def prepare_summary(patient_id: str | None = None) -> str:
    return _prepare_summary.run(patient_id, _get_container())


@mcp.tool(
    description=(
        "Export a previously generated summary as PDF, markdown, or JSON. "
        "Use the summary_id returned by prepare_summary. "
        "PDF is returned as base64-encoded content; markdown and JSON are returned as text."
    )
)
def export_summary(summary_id: str, format: str, patient_id: str | None = None) -> str:
    return _export.run(summary_id, format, patient_id, _get_container())
