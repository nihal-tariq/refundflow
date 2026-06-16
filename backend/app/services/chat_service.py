"""Chat service — the conversational entry point to the refund agent.

Bridges a free-text customer message to a structured agent run. When the turn
carries enough information (order + reason) it triggers the full LangGraph
execution and phrases the verdict via :class:`LLMService`; otherwise it returns a
helpful prompt for the missing details. No adjudication logic lives here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.observability.events import EventType
from app.observability.logging import get_logger
from app.repositories.customer_repository import CustomerRepository
from app.repositories.trace_repository import TraceRepository
from app.schemas.refund import ChatRequest, ChatResponse, RefundRequest
from app.services.llm_service import LLMService
from app.services.refund_service import RefundService
from app.tools.order_lookup import OrderLookupError, OrderLookupTool

_logger = get_logger(__name__)


@dataclass
class ChatSessionState:
    """In-memory conversational state for one customer chat session."""

    customer_id: str | None = None
    messages: list[dict[str, str]] = field(default_factory=list)
    order_id: str | None = None
    reason: str | None = None
    evidence_provided: bool = False
    refund_runs: int = 0
    last_decision: str | None = None
    last_order_id: str | None = None

    def bind_customer(self, customer_id: str) -> None:
        """Reset customer-specific state when a conversation changes accounts."""
        if self.customer_id in (None, customer_id):
            self.customer_id = customer_id
            return
        self.customer_id = customer_id
        self.messages.clear()
        self.order_id = None
        self.reason = None
        self.evidence_provided = False
        self.refund_runs = 0
        self.last_decision = None
        self.last_order_id = None


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
        state.bind_customer(request.customer_id)
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

        # 1. Classify intent
        intent = self._llm.classify_intent(message)

        # 2. Handle frustration/abuse
        if intent == "FRUSTRATION":
            reply = self._llm.phrase_empathy(customer.name, message)
            return self._reply(
                session_id=session_id,
                conversation_id=conversation_id,
                state=state,
                reply=reply,
                llm_used=self._llm.active,
            )

        # 3. Handle gratitude
        if intent == "GRATITUDE":
            return self._reply(
                session_id=session_id,
                conversation_id=conversation_id,
                state=state,
                reply=(
                    f"You're welcome, {customer.name.split()[0]}! I'm glad I could "
                    "help. Let me know if you need help with anything else."
                ),
            )

        resolution = None

        # 4. Handle follow-up queries on completed refund request sessions.
        # A new refund request or a new order reference starts a fresh refund
        # flow in the same conversation instead of getting trapped as follow-up.
        if state.last_decision:
            if intent in {"REFUND_REQUEST", "OTHER"}:
                resolution = self._llm.resolve_order(
                    message, self._orders.for_customer(request.customer_id)
                )
                if (
                    resolution.order_id
                    or resolution.mentioned_order_id
                    or resolution.candidates
                    or intent == "REFUND_REQUEST"
                ):
                    state.last_decision = None
                    state.last_order_id = None
                else:
                    resolution = None

            if state.last_decision is None:
                pass
            else:
                # Continue the conversation in the context of the last decision.
                # The chat loop keeps the message history in LangGraph state, so
                # the bot remembers the back-and-forth instead of replaying the
                # same answer to every follow-up (e.g. "connect", "bye").
                reply = await self._llm.converse(
                    conversation_id=conversation_id,
                    customer_name=customer.name,
                    message=message,
                    last_decision=state.last_decision,
                    last_order_id=state.last_order_id,
                )
                return self._reply(
                    session_id=session_id,
                    conversation_id=conversation_id,
                    state=state,
                    reply=reply,
                    llm_used=self._llm.active,
                )

        # 5. Normal slot-filling logic for new/incomplete sessions.
        order_id = _normalize_explicit_order_id(request.order_id)
        # Free text is interpreted by the LLM resolver, boxed to this customer's
        # actual orders. It can match ids, product references, and stated reasons.
        if not order_id and not state.order_id and intent != "GREETING":
            resolution = resolution or self._llm.resolve_order(
                message, self._orders.for_customer(request.customer_id)
            )
            if resolution.candidates and not resolution.order_id:
                return self._reply(
                    session_id=session_id,
                    conversation_id=conversation_id,
                    state=state,
                    reply=self._clarify_candidates(resolution.candidates),
                )
            order_id = resolution.order_id or resolution.mentioned_order_id
            if order_id and resolution.reason and not request.reason:
                state.reason = resolution.reason

        if order_id:
            state.order_id = order_id
            if not state.reason:
                state.reason = request.reason.strip() if request.reason else state.reason
            state.evidence_provided = request.evidence_provided
        elif request.reason:
            state.reason = request.reason.strip()
            state.evidence_provided = request.evidence_provided
        elif state.order_id and intent != "GREETING":
            state.reason = message

        if not state.order_id:
            return self._reply(
                session_id=session_id,
                conversation_id=conversation_id,
                state=state,
                reply=(
                    f"Hi {customer.name.split()[0]}! I can help with a refund. "
                    "Please send the order ID (like ORD-1001), or just tell me "
                    "which item it was."
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
        if self._llm.active:
            self._record_llm_response(db, session_id, detail.decision.value, reply)
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
            llm_used=self._llm.active,
        )

    def _clarify_candidates(self, candidates: list[str]) -> str:
        """Ask the customer to pick when a reference matched several orders."""
        labels: list[str] = []
        for cid in candidates[:4]:
            try:
                order = self._orders.run(cid)
                labels.append(f"{cid} ({order.product_name})")
            except OrderLookupError:
                labels.append(cid)
        if len(labels) > 1:
            joined = f"{', '.join(labels[:-1])}, or {labels[-1]}"
        else:
            joined = labels[0]
        return (
            "I found a few orders that could match — which one did you mean? "
            f"For example: {joined}."
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
        llm_used: bool = False,
    ) -> ChatResponse:
        """Record an assistant response and build the API response."""
        state.messages.append({"role": "assistant", "content": reply})
        return ChatResponse(
            session_id=session_id,
            conversation_id=conversation_id,
            reply=reply,
            decision=decision,
            decision_detail=decision_detail,
            llm_used=llm_used,
        )

    def _record_llm_response(
        self, db: Session, session_id: str, decision: str, reply: str
    ) -> None:
        """Persist an ``llm_response`` trace event for the refund session.

        Surfaces in the admin dashboard alongside the deterministic tool calls so
        operators can see exactly where the LLM phrasing layer (not the decision
        engine) shaped the customer-facing reply. Best-effort: a failure here must
        never break the chat reply.
        """
        try:
            TraceRepository(db).add_event(
                session_id=session_id,
                event_type=EventType.LLM_RESPONSE.value,
                node_name="decision",
                tool_name=f"{self._llm.provider}:{self._llm.model}",
                message=f"LLM phrased the {decision} reply",
                payload={
                    "provider": self._llm.provider,
                    "model": self._llm.model,
                    "decision": decision,
                    "reply": reply,
                },
            )
        except Exception as exc:  # pragma: no cover - observability must not throw
            _logger.warning("llm_response_event_failed", session_id=session_id, error=str(exc))


def _normalize_explicit_order_id(order_id: str | None) -> str | None:
    """Normalize an explicit structured order id field."""
    if not order_id:
        return None
    return order_id.strip().upper()
