"""list_biomarkers MCP tool — return all biomarkers the patient has data for."""

from __future__ import annotations

from src.mcp_server.tools._guard import get_patient_id
from src.orchestration import ServiceContainer, list_biomarkers_workflow


def run(container: ServiceContainer, filter: str | None = None) -> str:
    items = list_biomarkers_workflow(get_patient_id(), container, filter=filter)

    if not items:
        return "No biomarker records found for this patient."

    lines = [f"Found {len(items)} biomarker(s):\n"]
    for item in items:
        name = item["canonical_biomarker_id"] or item["original_name"]
        value = item["latest_value"]
        unit = item["latest_unit"] or ""
        date_str = item["latest_date"] or "unknown date"
        count = item["record_count"]
        lines.append(
            f"  {name}: {value} {unit}".rstrip() + f"  (latest: {date_str}, {count} record(s))"
        )
    return "\n".join(lines)
