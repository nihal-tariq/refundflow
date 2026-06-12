"""Refund and chat routes — the agent execution entry points."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.dependencies import get_chat_service, get_refund_service
from app.models.base import get_db
from app.schemas.refund import (
    ChatRequest,
    ChatResponse,
    RefundDecisionResponse,
    RefundRequest,
)
from app.services.chat_service import ChatService
from app.services.refund_service import RefundService

router = APIRouter(tags=["refunds"])


@router.post(
    "/refund-request",
    response_model=RefundDecisionResponse,
    summary="Run the refund agent on a request",
)
async def submit_refund(
    request: RefundRequest,
    db: Session = Depends(get_db),
    service: RefundService = Depends(get_refund_service),
) -> RefundDecisionResponse:
    """Execute the LangGraph refund agent and return its decision.

    The route is a thin adapter: it delegates entirely to the refund service.
    """
    return await service.process_refund(request, db)


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Conversational refund turn",
)
async def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    """Handle one conversational turn with the agent."""
    return await service.handle(request, db)
