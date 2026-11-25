"""Shared service wiring.

Single place where services are constructed and reused, so API routers
and the demo script all get the same configured instances. Instances
are cached on app.state after first construction.
"""

from fastapi import FastAPI

from app.config import get_settings
from app.services.anthropic_service import AnthropicService
from app.services.audit_service import AuditLogService
from app.services.conversation_service import ConversationService
from app.services.embedding_service import EmbeddingService
from app.services.search_service import SearchService
from app.services.support_assistant_service import SupportAssistantService
from app.services.takeover_service import TakeoverService
from app.services.ticket_service import TicketService
from app.services.triage_service import TriageService
from app.services.vector_store import VectorStore


def initialize_services(app: FastAPI) -> tuple:
    """Build (or fetch from app.state) all assistant services."""
    if getattr(app.state, "it_copilot_initialized", False):
        return (
            app.state.support_assistant_service,
            app.state.takeover_service,
        )

    settings = get_settings()

    anthropic_service = AnthropicService()
    embedding_service = EmbeddingService()
    vector_store = VectorStore(
        storage_directory=settings.vector_store_directory,
    )
    search_service = SearchService(
        embedding_service=embedding_service,
        vector_store=vector_store,
    )
    triage_service = TriageService(
        anthropic_service=anthropic_service,
    )
    conversation_service = ConversationService(
        database_path=settings.database_path,
    )
    ticket_service = TicketService(
        database_path=settings.database_path,
    )
    audit_service = AuditLogService(
        log_path=settings.audit_log_path,
    )
    takeover_service = TakeoverService()

    support_assistant_service = SupportAssistantService(
        triage_service=triage_service,
        search_service=search_service,
        anthropic_service=anthropic_service,
        conversation_service=conversation_service,
        ticket_service=ticket_service,
        audit_service=audit_service,
        takeover_service=takeover_service,
    )

    app.state.support_assistant_service = support_assistant_service
    app.state.takeover_service = takeover_service
    app.state.it_copilot_initialized = True

    return support_assistant_service, takeover_service


def get_services() -> tuple:
    """Return (SupportAssistantService, TakeoverService)."""
    from app.main import app

    return initialize_services(app)


def get_support_assistant_service() -> SupportAssistantService:
    support_assistant_service, _ = get_services()
    return support_assistant_service
