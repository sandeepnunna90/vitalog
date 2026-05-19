"""query_records MCP tool — answer a natural-language question over stored records."""

from __future__ import annotations

from src.mcp_server.tools._guard import validate_patient_id
from src.orchestration import ServiceContainer, query_workflow


def run(patient_id: str | None, question: str, container: ServiceContainer) -> str:
    pid = validate_patient_id(patient_id)
    response = query_workflow(pid, question, container)
    return response.text
