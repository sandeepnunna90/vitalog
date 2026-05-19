"""upload_document MCP tool — ingest a lab report from file path or base64 content."""

from __future__ import annotations

import base64
import re
from pathlib import Path

from src.mcp_server.tools._guard import PATIENT_ID
from src.orchestration import ServiceContainer, upload_document_workflow


def run(
    file_content_base64: str | None,
    filename: str | None,
    container: ServiceContainer,
    *,
    file_path: str | None = None,
) -> str:
    if file_path is not None:
        try:
            file_bytes = Path(file_path).read_bytes()
        except OSError as exc:
            return f"Error: could not read file at {file_path!r}: {exc}"
    elif file_content_base64 is not None:
        # ~7 MB decoded limit; base64 overhead is ~4/3, so cap at 10 MB encoded.
        if len(file_content_base64) > 10 * 1024 * 1024:
            return "Error: file too large (max ~7 MB)."
        # Strip everything that is not a valid base64 character. Claude Desktop injects
        # various whitespace and escape sequences (\n, \\n, \r) as line separators;
        # enumerating them is fragile. Keeping only [A-Za-z0-9+/=] is exhaustive.
        sanitized = re.sub(r"[^A-Za-z0-9+/=]", "", file_content_base64)
        # Re-add padding — some encoders omit trailing = and b64decode requires it.
        padding_needed = (4 - len(sanitized) % 4) % 4
        sanitized += "=" * padding_needed
        try:
            file_bytes = base64.b64decode(sanitized, validate=False)
        except Exception as exc:
            return (
                f"Error: file_content_base64 is not valid base64 "
                f"(len={len(sanitized)}, padding_added={padding_needed}, err={exc})."
            )
    else:
        # No path or base64 given — pick the newest PDF from ~/Downloads.
        downloads = Path.home() / "Downloads"
        candidates = sorted(downloads.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not candidates:
            return "No PDF found in ~/Downloads/. Place the lab report there and try again."
        detected = candidates[0]
        try:
            file_bytes = detected.read_bytes()
        except OSError as exc:
            return f"Error reading {detected.name}: {exc}"
        filename = filename or detected.name

    result = upload_document_workflow(file_bytes, filename or "document.pdf", PATIENT_ID, container)

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
