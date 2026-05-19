"""upload_document MCP tool — decode base64 file and run the full ingestion pipeline."""

from __future__ import annotations

import base64
from pathlib import Path

from src.mcp_server.tools._guard import validate_patient_id
from src.orchestration import ServiceContainer, upload_document_workflow


def run(
    file_content_base64: str,
    filename: str,
    patient_id: str,
    container: ServiceContainer,
    file_path: str | None = None,
) -> str:
    pid = validate_patient_id(patient_id)

    if file_path:
        # Local shortcut: read file directly from disk (avoids base64 encoding issues).
        p = Path(file_path)
        if not p.exists():
            return f"Error: file not found at path {file_path!r}"
        file_bytes = p.read_bytes()
        resolved_filename = filename or p.name
    else:
        # ~7 MB decoded limit; base64 overhead is ~4/3, so cap at 10 MB encoded.
        if len(file_content_base64) > 10 * 1024 * 1024:
            return "Error: file too large (max ~7 MB)."
        # Claude Desktop injects literal \n (backslash + n) as line separators in base64
        # strings. Strip those and any real whitespace before decoding.
        sanitized = file_content_base64.replace("\\n", "").replace("\n", "").replace("\r", "")
        try:
            file_bytes = base64.b64decode(sanitized)
        except Exception:
            return "Error: file_content_base64 is not valid base64."
        resolved_filename = filename

    result = upload_document_workflow(file_bytes, resolved_filename, pid, container)

    lines = [f"Document processed ({result.category})."]
    if result.auto_accepted or result.pending_user or result.rejected or result.pending_taxonomy:
        lines.append(
            f"  {result.auto_accepted} auto-accepted, "
            f"{result.pending_user} pending user review, "
            f"{result.pending_taxonomy} pending taxonomy, "
            f"{result.rejected} rejected."
        )
    if result.duplicate_skipped:
        lines.append(f"  {result.duplicate_skipped} duplicate(s) skipped (already on record).")
    if result.document_id:
        lines.append(f"  Document ID: {result.document_id}")
    lines.append(result.user_message)
    return "\n".join(lines)
