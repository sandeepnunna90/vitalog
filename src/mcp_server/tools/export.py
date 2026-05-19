"""export_summary MCP tool — export a persisted summary as PDF, markdown, or JSON."""

from __future__ import annotations

import base64
import uuid

from src.mcp_server.tools._guard import PATIENT_ID
from src.orchestration import ServiceContainer, export_workflow

_VALID_FORMATS = frozenset({"pdf", "markdown", "json"})


def run(summary_id: str, format: str, container: ServiceContainer) -> str:
    if format not in _VALID_FORMATS:
        return f"Unsupported format {format!r}. Choose from: pdf, markdown, json."
    try:
        sid = uuid.UUID(summary_id)
    except ValueError:
        return f"Invalid summary_id: {summary_id!r}"

    try:
        data = export_workflow(sid, format, PATIENT_ID, container)
    except ValueError as exc:
        return f"Export failed: {exc}"

    if format == "pdf":
        encoded = base64.b64encode(data).decode("ascii")
        return (
            f"PDF export ready ({len(data):,} bytes).\n"
            f"Base64-encoded content (save as .pdf):\n{encoded}"
        )
    return data.decode("utf-8")
