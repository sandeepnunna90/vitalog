"""get_trend MCP tool — return longitudinal trend + guideline bands."""

from __future__ import annotations

import json

from src.mcp_server.tools._guard import validate_patient_id
from src.orchestration import ServiceContainer, view_trend_workflow


def run(patient_id: str | None, biomarker_id: str, container: ServiceContainer) -> str:
    pid = validate_patient_id(patient_id)
    trend = view_trend_workflow(pid, biomarker_id, container)

    points = [
        {
            "date": p.collection_date.isoformat(),
            "value": p.canonical_value,
            "unit": p.canonical_unit,
            "lab_source": p.lab_source,
        }
        for p in trend.points
    ]
    bands = [
        {
            "label": b.label,
            "lower": b.lower,
            "upper": b.upper,
            "raw_range": b.raw_range,
            "citation": b.citation,
        }
        for b in trend.bands
    ]
    payload = {
        "biomarker_id": biomarker_id,
        "point_count": len(points),
        "points": points,
        "bands": bands,
    }
    return json.dumps(payload, indent=2)
