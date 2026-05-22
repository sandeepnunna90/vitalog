"""query_records MCP tool — answer a natural-language question over stored records."""

from __future__ import annotations

from src.mcp_server.tools._guard import get_patient_id
from src.orchestration import ServiceContainer, query_workflow


def run(question: str, container: ServiceContainer) -> str:
    response = query_workflow(get_patient_id(), question, container)
    return response.text
