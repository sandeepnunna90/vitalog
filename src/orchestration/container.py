"""Service container for the orchestration layer.

Builds all application services from environment variables once per process.
The MCP server calls build_container() on first tool invocation; subsequent
calls return the cached instance via lru_cache.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from src.gateway.gateway import Gateway
from src.ingestion.classifier import DocumentClassifier
from src.ingestion.storage_router import StorageRouter
from src.ingestion.structurer import Structurer
from src.ingestion.textract_adapter import TextractAdapter
from src.ingestion.textract_fallback import TextractFallbackAdapter
from src.ingestion.upload_validator import UploadValidator
from src.intelligence.annotator import SummaryAnnotator
from src.intelligence.nlq_handler import NlqHandler
from src.intelligence.summary_generator import SummaryGenerator
from src.intelligence.trend_engine import TrendEngine
from src.normalization.duplicate_detector import DuplicateDetector
from src.normalization.pending_queue import PendingQueue
from src.persistence.audit_log_repository import AuditLogRepository
from src.persistence.biomarker_repository import BiomarkerRepository
from src.persistence.document_repository import DocumentRepository
from src.persistence.document_store import DocumentStore
from src.persistence.summary_repository import SummaryRepository
from src.persistence.supabase_client import get_service_client
from src.persistence.taxonomy_repository import TaxonomyRepository


@dataclass
class ServiceContainer:
    # Persistence
    biomarker_repo: BiomarkerRepository
    summary_repo: SummaryRepository
    document_repo: DocumentRepository
    audit_repo: AuditLogRepository
    taxonomy_repo: TaxonomyRepository
    document_store: DocumentStore
    # Ingestion
    validator: UploadValidator
    classifier: DocumentClassifier
    storage_router: StorageRouter
    textract: TextractAdapter
    fallback: TextractFallbackAdapter
    structurer: Structurer
    # Normalization
    dedup: DuplicateDetector
    pending_queue: PendingQueue
    # Intelligence
    trend_engine: TrendEngine
    nlq_handler: NlqHandler
    summary_generator: SummaryGenerator
    annotator: SummaryAnnotator


@lru_cache(maxsize=1)
def build_container() -> ServiceContainer:
    """Construct and return the singleton service container.

    Reads SUPABASE_URL, SUPABASE_SERVICE_KEY, and ANTHROPIC_API_KEY from the
    environment. Raises KeyError if any required variable is missing.
    """
    client = get_service_client()
    api_key = os.environ["ANTHROPIC_API_KEY"]

    # Persistence
    audit_repo = AuditLogRepository(client)
    biomarker_repo = BiomarkerRepository(client)
    summary_repo = SummaryRepository(client)
    document_repo = DocumentRepository(client)
    taxonomy_repo = TaxonomyRepository(client)
    document_store = DocumentStore(client)

    # Gateway (shared by classifier, structurer, fallback, nlq, summary)
    gateway = Gateway(audit_repo=audit_repo, api_key=api_key)

    # Ingestion
    validator = UploadValidator(audit_repo=audit_repo)
    classifier = DocumentClassifier(gateway=gateway)
    storage_router = StorageRouter(
        document_store=document_store,
        doc_repo=document_repo,
        audit_repo=audit_repo,
    )
    textract = TextractAdapter(audit_repo=audit_repo)
    fallback = TextractFallbackAdapter(gateway=gateway, audit_repo=audit_repo)
    structurer = Structurer(gateway=gateway, audit_repo=audit_repo)

    # Normalization
    dedup = DuplicateDetector(biomarker_repo=biomarker_repo, audit_repo=audit_repo)
    pending_queue = PendingQueue(taxonomy_repo=taxonomy_repo)

    # Intelligence
    trend_engine = TrendEngine(biomarker_repo=biomarker_repo)
    nlq_handler = NlqHandler(
        gateway=gateway,
        biomarker_repo=biomarker_repo,
        audit_repo=audit_repo,
    )
    summary_generator = SummaryGenerator(
        gateway=gateway,
        biomarker_repo=biomarker_repo,
        audit_repo=audit_repo,
    )
    annotator = SummaryAnnotator(summary_repo=summary_repo, audit_repo=audit_repo)

    return ServiceContainer(
        biomarker_repo=biomarker_repo,
        summary_repo=summary_repo,
        document_repo=document_repo,
        audit_repo=audit_repo,
        taxonomy_repo=taxonomy_repo,
        document_store=document_store,
        validator=validator,
        classifier=classifier,
        storage_router=storage_router,
        textract=textract,
        fallback=fallback,
        structurer=structurer,
        dedup=dedup,
        pending_queue=pending_queue,
        trend_engine=trend_engine,
        nlq_handler=nlq_handler,
        summary_generator=summary_generator,
        annotator=annotator,
    )
