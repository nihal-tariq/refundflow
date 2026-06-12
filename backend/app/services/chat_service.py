"""Chat service — the conversational entry point to the refund agent.

Bridges a free-text customer message to a structured agent run. When the turn
carries enough information (order + reason) it triggers the full LangGraph
execution and phrases the verdict via :class:`LLMService`; otherwise it returns a
helpful prompt for the missing details. No adjudication logic lives here.
"""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from app.repositories.customer_repository import CustomerRepository
from app.schemas.refund import ChatRequest, ChatResponse, RefundRequest
from app.services.llm_service import LLMService
from app.services.refund_service import RefundService


class ChatService:
    """Turns conversational requests into agent executions and replies."""

    def __init__(
        self,
        refund_service: RefundService | None = None,
        llm_service: LLMService | None = None,
        customer_repo: CustomerRepository | None = None,
    ) -> None:
        """Inject collaborators (defaults wire production instances)."""
        self._refunds = refund_service or RefundService()
        self._llm = llm_service or LLMService()
        self._customers = customer_repo or CustomerRepository()

    async def handle(self, request: ChatRequest, db: Session) -> ChatResponse:
        """Process one chat turn and return the agent's reply.

        Args:
            request: The chat request (customer id, message, optional order/reason).
            db: Active SQLAlchemy session.

        Returns:
            A :class:`ChatResponse`, including a decision when one was produced.
        """
        session_id = request.session_id or f"sess-{uuid4().hex[:12]}"
        customer = self._customers.get(request.customer_id)
        if customer is None:
            return ChatResponse(
                session_id=session_id,
                reply=(
                    f"I couldn't find an account for '{request.customer_id}'. "
                    "Please double-check your customer ID."
                ),
            )

        if not request.order_id or not (request.reason or request.message):
            return ChatResponse(
                session_id=session_id,
                reply=(
                    f"Hi {customer.name.split()[0]}! I can help with that. Could "
                    "you share your order ID (it looks like ORD-1001) and briefly "
                    "tell me what went wrong?"
                ),
            )

        refund_request = RefundRequest(
            customer_id=request.customer_id,
            order_id=request.order_id,
            reason=request.reason or request.message,
            evidence_provided=request.evidence_provided,
        )
        detail = await self._refunds.process_refund(refund_request, db, session_id)
        reply = self._llm.phrase_decision(
            customer.name,
            detail.decision,
            order=detail.order,
            reason_codes=detail.reason_codes,
            rationale=detail.rationale,
        )
        return ChatResponse(
            session_id=session_id,
            reply=reply,
            decision=detail.decision,
            decision_detail=detail,
        )
