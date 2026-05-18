"""F6 top-level export dispatcher — routes format to the appropriate exporter."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from src.intelligence.exporters.json_exporter import export_json
from src.intelligence.exporters.markdown_exporter import export_markdown
from src.intelligence.exporters.pdf_exporter import export_pdf
from src.persistence.summary_repository import SummaryRepository

_FORMATS = frozenset({"pdf", "markdown", "json"})

_audit_log = logging.getLogger("audit")


def export_summary(
    summary_id: uuid.UUID,
    format: str,
    summary_repo: SummaryRepository,
    audit_repo: Any | None = None,
) -> bytes:
    """Export a persisted summary in the requested format.

    Returns raw bytes (PDF, UTF-8 markdown, or UTF-8 JSON).
    Raises ValueError for unknown format or missing summary_id.
    Logs event_type='summary_exported' to audit log (AC6).
    """
    if format not in _FORMATS:
        raise ValueError(f"Unsupported format: {format!r}. Choose from: {sorted(_FORMATS)}")

    row = summary_repo.get(summary_id)
    if row is None:
        raise ValueError(f"Summary {summary_id} not found")

    if format == "pdf":
        data = export_pdf(row)
    elif format == "markdown":
        data = export_markdown(row)
    else:
        data = export_json(row)

    _log_export_audit(summary_id, format, len(data), audit_repo)
    return data


def _log_export_audit(
    summary_id: uuid.UUID,
    format: str,
    byte_size: int,
    audit_repo: Any | None,
) -> None:
    _audit_log.info(
        "summary_exported",
        extra={"summary_id": str(summary_id), "format": format, "byte_size": byte_size},
    )
    if audit_repo is not None:
        try:
            audit_repo.record(
                actor="system",
                event_type="summary_exported",
                payload={
                    "summary_id": str(summary_id),
                    "format": format,
                    "byte_size": byte_size,
                },
            )
        except Exception as _exc:  # noqa: BLE001
            _audit_log.warning("audit_log_failed: %s", _exc)
