"""Orchestration layer — workflow coordinators that compose service calls.

Each workflow is a thin coordinator: validate inputs, call services in order,
return a typed result. No business logic; no persistence calls from this
package directly (all go through the ServiceContainer).
"""

from src.orchestration.container import ServiceContainer, build_container
from src.orchestration.workflows import (
    GenerateSummaryResult,
    UploadResult,
    export_workflow,
    generate_summary_workflow,
    list_biomarkers_workflow,
    query_workflow,
    upload_document_workflow,
    view_trend_workflow,
)

__all__ = [
    "ServiceContainer",
    "build_container",
    "UploadResult",
    "GenerateSummaryResult",
    "upload_document_workflow",
    "list_biomarkers_workflow",
    "view_trend_workflow",
    "query_workflow",
    "generate_summary_workflow",
    "export_workflow",
]
