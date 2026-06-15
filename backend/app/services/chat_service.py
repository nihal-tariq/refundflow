"""Chat service — the conversational entry point to the refund agent.

Bridges a free-text customer message to a structured agent run. When the turn
carries enough information (order + reason) it triggers the full LangGraph
execution and phrases the verdict via :class:`LLMService`; otherwise it returns a
helpful prompt for the missing details. No adjudication logic lives here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.repositories.customer_repository import CustomerRepository
from app.schemas.refund import ChatRequest, ChatResponse, RefundRequest
from app.services.llm_service import LLMService
from app.services.refund_service import RefundService
from app.tools.order_lookup import OrderLookupError, OrderLookupTool

_THANKS_RE = re.compile(
    r"^\s*(thanks|thank you|thx|ty|appreciate it|much appreciated)[!. ]*\s*$",
    re.IGNORECASE,
)
_GREETING_RE = re.compile(
    r"^\s*(hi|hello|hey|good morning|good afternoon)[!. ]*\s*$",
    re.IGNORECASE,
)
_ORDER_ID_RE = re.compile(r"\bORD-\d{4,}\b", re.IGNORECASE)
_REFUND_WORDS = ("refund", "return", "money back", "exchange")


@dataclass
class ChatSessionState:
    """In-memory conversational state for one customer chat session."""

    messages: list[dict[str, str]] = field(default_factory=list)
    order_id: str | None = None
    reason: str | None = None
    evidence_provided: bool = False
    refund_runs: int = 0
    last_decision: str | None = None
    last_order_id: str | None = None


class ChatService:
    """Turns conversational requests into agent executions and replies."""

    def __init__(
        self,
        refund_service: RefundService | None = None,
        llm_service: LLMService | None = None,
        customer_repo: CustomerRepository | None = None,
        order_tool: OrderLookupTool | None = None,
    ) -> None:
        """Inject collaborators (defaults wire production instances)."""
        self._refunds = refund_service or RefundService()
        self._llm = llm_service or LLMService()
        self._customers = customer_repo or CustomerRepository()
        self._orders = order_tool or OrderLookupTool()
        self._sessions: dict[str, ChatSessionState] = {}

    async def handle(self, request: ChatRequest, db: Session) -> ChatResponse:
        """Process one chat turn and return the agent's reply.

        Args:
            request: The chat request (customer id, message, optional order/reason).
            db: Active SQLAlchemy session.

        Returns:
            A :class:`ChatResponse`, including a decision when one was produced.
        """
        session_id = request.session_id or f"sess-{uuid4().hex[:12]}"
        conversation_id = request.conversation_id or session_id
        state = self._sessions.setdefault(conversation_id, ChatSessionState())
        message = request.message.strip()
        state.messages.append({"role": "user", "content": message})

        customer = self._customers.get(request.customer_id)
        if customer is None:
            return self._reply(
                session_id=session_id,
                conversation_id=conversation_id,
                state=state,
                reply=(
                    f"I couldn't find an account for '{request.customer_id}'. "
                    "Please double-check your customer ID."
                ),
            )

        if _is_gratitude(message):
            return self._reply(
                session_id=session_id,
                conversation_id=conversation_id,
                state=state,
                reply=(
                    f"You're welcome, {customer.name.split()[0]}! I'm glad I could "
                    "help. If you need to check another refund, send me the order ID."
                ),
            )

        order_id = _normalize_order_id(request.order_id) or _extract_order_id(message)
        if order_id:
            state.order_id = order_id
            state.reason = (
                request.reason.strip()
                if request.reason
                else _reason_from_message(message, order_id)
            )
            state.evidence_provided = request.evidence_provided
        elif request.reason:
            state.reason = request.reason.strip()
            state.evidence_provided = request.evidence_provided
        elif state.order_id and not _is_greeting(message):
            state.reason = message

        if not state.order_id:
            return self._reply(
                session_id=session_id,
                conversation_id=conversation_id,
                state=state,
                reply=(
                    f"Hi {customer.name.split()[0]}! I can help with a refund. "
                    "Please send the order ID, like ORD-1001."
                ),
            )

        try:
            order = self._orders.run(state.order_id)
        except OrderLookupError:
            bad_order = state.order_id
            state.order_id = None
            state.reason = None
            return self._reply(
                session_id=session_id,
                conversation_id=conversation_id,
                state=state,
                reply=(
                    f"I couldn't find order {bad_order}. Please check the order ID "
                    "and send it again."
                ),
            )

        if order.customer_id != request.customer_id:
            bad_order = state.order_id
            state.order_id = None
            state.reason = None
            return self._reply(
                session_id=session_id,
                conversation_id=conversation_id,
                state=state,
                reply=(
                    f"Order {bad_order} does not appear to belong to this account. "
                    "Please send an order ID from your account."
                ),
            )

        if not state.reason:
            return self._reply(
                session_id=session_id,
                conversation_id=conversation_id,
                state=state,
                reply=(
                    f"I found {order.product_name} ({state.order_id}). What is the "
                    "reason you'd like a refund?"
                ),
            )

        refund_request = RefundRequest(
            customer_id=request.customer_id,
            order_id=state.order_id,
            reason=state.reason,
            evidence_provided=state.evidence_provided,
        )
        detail = await self._refunds.process_refund(refund_request, db, session_id)
        reply = self._llm.phrase_decision(
            customer.name,
            detail.decision,
            order=detail.order,
            reason_codes=detail.reason_codes,
            rationale=detail.rationale,
        )
        state.refund_runs += 1
        state.last_decision = detail.decision.value
        state.last_order_id = detail.order.order_id if detail.order else state.order_id
        state.order_id = None
        state.reason = None
        state.evidence_provided = False
        return self._reply(
            session_id=session_id,
            conversation_id=conversation_id,
            state=state,
            reply=reply,
            decision=detail.decision,
            decision_detail=detail,
        )

    def _reply(
        self,
        *,
        session_id: str,
        conversation_id: str,
        state: ChatSessionState,
        reply: str,
        decision: Any = None,
        decision_detail: Any = None,
    ) -> ChatResponse:
        """Record an assistant response and build the API response."""
        state.messages.append({"role": "assistant", "content": reply})
        return ChatResponse(
            session_id=session_id,
            conversation_id=conversation_id,
            reply=reply,
            decision=decision,
            decision_detail=decision_detail,
        )


def _is_gratitude(message: str) -> bool:
    """Return whether ``message`` is a simple acknowledgement, not a refund turn."""
    return bool(_THANKS_RE.match(message))


def _is_greeting(message: str) -> bool:
    """Return whether ``message`` is a simple greeting."""
    return bool(_GREETING_RE.match(message))


def _normalize_order_id(order_id: str | None) -> str | None:
    """Normalize an explicit order id field."""
    if not order_id:
        return None
    match = _ORDER_ID_RE.search(order_id)
    return match.group(0).upper() if match else order_id.strip().upper()


def _extract_order_id(message: str) -> str | None:
    """Extract an order id from a free-text message."""
    match = _ORDER_ID_RE.search(message)
    return match.group(0).upper() if match else None


def _reason_from_message(message: str, order_id: str) -> str | None:
    """Use surrounding free text as a reason when the message is more than an id."""
    cleaned = _ORDER_ID_RE.sub("", message).strip(" .,-:")
    lowered = cleaned.lower()
    filler = ("refund", "return", "order", "for", "please", "i want", "i need")
    if not cleaned or lowered in filler:
        return None
    if len(cleaned.split()) < 3 and not _looks_like_refund_reason(cleaned):
        return None
    return message.strip()


def _looks_like_refund_reason(message: str) -> bool:
    """Heuristic for messages that should fill the refund-reason slot."""
    lowered = message.lower()
    return any(word in lowered for word in _REFUND_WORDS) or len(message.split()) >= 3
