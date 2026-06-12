"""Concrete dependency providers used by route handlers.

Services that own stateful, expensive resources (the LangGraph agent + its
checkpointer) are process-wide singletons so checkpoint state survives across
requests. Request-scoped services (those needing a DB session) are built per
call from the injected session.
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.models.base import get_db
from app.repositories.customer_repository import CustomerRepository
from app.services.chat_service import ChatService
from app.services.refund_service import RefundService
from app.services.trace_service import TraceService

# ── Process-wide singletons (stateful: agent checkpointer) ─────────────────
_refund_service = RefundService()
_chat_service = ChatService(refund_service=_refund_service)
_customer_repository = CustomerRepository()


def get_refund_service() -> RefundService:
    """Provide the shared refund service singleton."""
    return _refund_service


def get_chat_service() -> ChatService:
    """Provide the shared chat service singleton."""
    return _chat_service


def get_customer_repository() -> CustomerRepository:
    """Provide the shared customer repository singleton."""
    return _customer_repository


def get_trace_service(db: Session = Depends(get_db)) -> TraceService:
    """Provide a request-scoped trace service bound to the DB session."""
    return TraceService(db)
