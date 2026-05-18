"""JSON export for F6 — structured Summary + annotations for round-trip import."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from src.intelligence.annotator import _parse_annotations
from src.persistence.models import SummaryRow


def export_json(row: SummaryRow) -> bytes:
    """Render a SummaryRow to indented JSON bytes (UTF-8).

    Emits content_json (the stored Summary fields, including disclaimer and citations)
    merged with summary_id, patient_annotations, and exported_at timestamp.
    """
    annotations = [a.model_dump(mode="json") for a in _parse_annotations(row.patient_annotations)]
    payload = {
        **row.content_json,
        "summary_id": str(row.summary_id),
        "patient_annotations": annotations,
        "exported_at": datetime.now(UTC).isoformat(),
    }
    return json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")
