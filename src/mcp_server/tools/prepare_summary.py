"""prepare_summary MCP tool — generate and persist an appointment summary."""

from __future__ import annotations

from src.mcp_server.tools._guard import get_patient_id
from src.orchestration import ServiceContainer, generate_summary_workflow


def run(container: ServiceContainer) -> str:
    result = generate_summary_workflow(get_patient_id(), container)

    if result.is_fallback:
        return (
            f"Summary could not be fully generated (fallback mode).\n"
            f"Summary ID: {result.summary_id}\n\n"
            f"{result.disclaimer}"
        )

    sections = []
    if result.conditions_section:
        sections.append(f"**Conditions**\n{result.conditions_section}")
    if result.results_section:
        sections.append(f"**Lab Results**\n{result.results_section}")
    if result.trends_section:
        sections.append(f"**Trends**\n{result.trends_section}")
    if result.data_gaps_section:
        sections.append(f"**Data Gaps**\n{result.data_gaps_section}")
    if result.patient_notes:
        sections.append(f"**Patient Notes**\n{result.patient_notes}")

    body = "\n\n".join(sections)
    return (
        f"Summary generated ({result.citation_count} citation(s)).\n"
        f"Summary ID: {result.summary_id}  ← use this to export as PDF/markdown/JSON\n\n"
        f"{body}\n\n"
        f"---\n{result.disclaimer}"
    )
