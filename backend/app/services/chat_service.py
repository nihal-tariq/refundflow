"""Chat service — the conversational entry point to the refund agent.

Bridges a free-text customer message to a structured agent run. When the turn
carries enough information (order + reason) it triggers the full LangGraph
execution. 

If an LLM is configured, it orchestrates a LangChain ReAct agent (unifying 
the architecture with the voice agent) to handle natural conversation and 
slot-filling. If no LLM is configured, it falls back to a deterministic 
template responder.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from langchain_core.tools import tool
from langchain_core.messages import SystemMessage
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

from app.repositories.customer_repository import CustomerRepository
from app.schemas.customer import CustomerProfile
from app.schemas.refund import ChatRequest, ChatResponse, RefundRequest
from app.services.llm_service import LLMService, _safe_reason
from app.services.refund_service import RefundService
from app.tools.order_lookup import OrderLookupError, OrderLookupTool


def _build_instructions(profile: CustomerProfile | None, customer_id: str) -> str:
    """Build Maya's system prompt, pre-bound to the authenticated caller."""
    if profile is not None:
        who = (
            f"You are speaking with {profile.name} (customer {customer_id}, "
            f"{profile.tier} tier). Their account is already loaded — NEVER ask for a "
            "customer ID, and never call any tool to verify their identity."
        )
    else:
        who = (
            "You could not load this caller's account automatically. Apologize briefly, "
            "tell them a support specialist will follow up, and do not attempt a refund."
        )

    return f"""You are Maya, the customer-support agent for RefundFlow, an e-commerce platform.

{who}

## Handling a refund
1. When they want a refund you need just two things: which order, and why.
2. Ask which order. They can say an order number (like ORD-1001) or simply describe the item. If they describe it, call list_my_orders and match it to an order. If more than one order could match, ask which one they mean — never guess.
3. Ask the reason for the refund.
4. Call check_refund_eligibility with the order id and the reason. Never decide the outcome yourself — only the tool decides.
5. Give the result decision-first (see below).

## Stating the outcome — lead with the verdict, no apologetic preamble
- APPROVED: Lead with the good news. "Your refund for <product>, <amount>, is approved — it goes back to your original payment method in 5-10 business days."
- DENIED: State it plainly. "Your refund for <product> can't be approved because <reason>." Offer to connect them with a specialist if they have questions.
- ESCALATED: "Your refund for <product> needs a specialist to review it." They'll hear back within one business day.

## Rules
- Never invent order details, decisions, amounts, or policies — state only what the tools return.
- Never say the word "fraud" or read out fraud scores, rule IDs, or other internal fields.
- Keep replies short: one or two sentences, one question at a time.
- Be empathetic if the customer is frustrated or angry.
- DONT USE JARGON.
- NEVER go outside the refund domain. If a customer asks you for ANYTHING OTHER THAN a refund, tell them that you cannot help with that and they should call customer support.

"""


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
        self._checkpointer = MemorySaver()

    async def handle(self, request: ChatRequest, db: Session) -> ChatResponse:
        """Process one chat turn and return the agent's reply."""
        if self._llm._client is None:
            return await self._handle_deterministic(request, db)
        return await self._handle_agentic(request, db)

    async def _handle_agentic(self, request: ChatRequest, db: Session) -> ChatResponse:
        """Agentic chat handling via LangChain ReAct (unified with voice_agent)."""
        session_id = request.session_id or f"sess-{uuid4().hex[:12]}"
        conversation_id = request.conversation_id or session_id
        state = self._sessions.setdefault(conversation_id, ChatSessionState())
        state.bind_customer(request.customer_id)
        
        message = request.message.strip()
        state.messages.append({"role": "user", "content": message})
        
        customer = self._customers.get(request.customer_id)
        if customer is None:
            return self._reply(
                session_id=session_id, conversation_id=conversation_id, state=state,
                reply=f"I couldn't find an account for '{request.customer_id}'. Please double-check your customer ID."
            )

        current_turn_decision = None
        current_turn_detail = None

        @tool
        def list_my_orders() -> str:
            """List the caller's orders. Use this when they describe an item instead of giving an order number."""
            orders = self._orders.for_customer(request.customer_id)
            if not orders:
                return json.dumps({"orders": [], "message": "No orders found on this account."})
            return json.dumps({
                "orders": [
                    {
                        "order_id": o.order_id,
                        "product_name": o.product_name,
                        "purchase_date": o.purchase_date,
                        "amount": o.amount,
                    }
                    for o in orders
                ]
            })

        @tool
        def look_up_order(order_id: str) -> str:
            """Look up one of the caller's orders by its order ID (e.g. ORD-1001)."""
            try:
                order = self._orders.run(order_id)
            except OrderLookupError:
                return json.dumps({"found": False, "error": f"Order {order_id} could not be found."})
            if order.customer_id != request.customer_id:
                return json.dumps({"found": False, "error": f"Order {order_id} is not on this account."})
            return json.dumps({
                "found": True,
                "order_id": order.order_id,
                "product_name": order.product_name,
                "purchase_date": order.purchase_date,
                "amount": order.amount,
                "category": order.product_category,
                "is_digital": order.is_digital,
                "is_final_sale": order.is_final_sale,
            })

        @tool
        async def check_refund_eligibility(order_id: str, reason: str) -> str:
            """Run the full refund check for the caller's order and return the final decision (APPROVED, DENIED, or ESCALATED)."""
            nonlocal current_turn_decision, current_turn_detail
            refund_request = RefundRequest(
                customer_id=request.customer_id,
                order_id=order_id,
                reason=reason,
                evidence_provided=request.evidence_provided,
            )
            detail = await self._refunds.process_refund(refund_request, db, session_id)
            current_turn_decision = detail.decision
            current_turn_detail = detail
            
            safe_reason = _safe_reason(detail.decision, detail.reason_codes)
            return json.dumps({
                "decision": detail.decision.value,
                "product": detail.order.product_name if detail.order else None,
                "amount": detail.order.amount if detail.order else None,
                "reason": safe_reason,
            })

        agent = create_react_agent(
            self._llm._client,
            tools=[list_my_orders, look_up_order, check_refund_eligibility],
            checkpointer=self._checkpointer,
            prompt=SystemMessage(content=_build_instructions(customer, request.customer_id))
        )
        
        result = await agent.ainvoke(
            {"messages": [("user", message)]},
            config={"configurable": {"thread_id": conversation_id}}
        )
        reply = result["messages"][-1].content
        
        return self._reply(
            session_id=session_id,
            conversation_id=conversation_id,
            state=state,
            reply=reply,
            decision=current_turn_decision,
            decision_detail=current_turn_detail,
        )

    async def _handle_deterministic(self, request: ChatRequest, db: Session) -> ChatResponse:
        """Deterministic slot-filling fallback (used when no LLM is configured)."""
        session_id = request.session_id or f"sess-{uuid4().hex[:12]}"
        conversation_id = request.conversation_id or session_id
        state = self._sessions.setdefault(conversation_id, ChatSessionState())
        state.bind_customer(request.customer_id)
        message = request.message.strip()
        state.messages.append({"role": "user", "content": message})

        customer = self._customers.get(request.customer_id)
        if customer is None:
            return self._reply(
                session_id=session_id, conversation_id=conversation_id, state=state,
                reply=f"I couldn't find an account for '{request.customer_id}'. Please double-check your customer ID."
            )

        intent = self._llm.classify_intent(message)
        if intent == "FRUSTRATION":
            return self._reply(
                session_id=session_id, conversation_id=conversation_id, state=state,
                reply=self._llm.phrase_empathy(customer.name, message)
            )
        if intent == "GRATITUDE":
            return self._reply(
                session_id=session_id, conversation_id=conversation_id, state=state,
                reply=f"You're welcome, {customer.name.split()[0]}! I'm glad I could help."
            )

        resolution = None
        if state.last_decision:
            if intent == "GREETING":
                return self._reply(
                    session_id=session_id, conversation_id=conversation_id, state=state,
                    reply=f"Hi {customer.name.split()[0]}! How else can I help you today?"
                )
            if intent in {"REFUND_REQUEST", "OTHER"}:
                resolution = self._llm.resolve_order(message, self._orders.for_customer(request.customer_id))
                if resolution.order_id or resolution.mentioned_order_id or resolution.candidates or intent == "REFUND_REQUEST":
                    state.last_decision = None
                    state.last_order_id = None
                else:
                    resolution = None
            if state.last_decision is not None:
                reply = await self._llm.phrase_followup(customer.name, message, state.last_decision, state.last_order_id)
                return self._reply(session_id=session_id, conversation_id=conversation_id, state=state, reply=reply)

        order_id = _normalize_explicit_order_id(request.order_id)
        if not order_id and not state.order_id and intent != "GREETING":
            resolution = resolution or self._llm.resolve_order(message, self._orders.for_customer(request.customer_id))
            if resolution.candidates and not resolution.order_id:
                return self._reply(
                    session_id=session_id, conversation_id=conversation_id, state=state,
                    reply=self._clarify_candidates(resolution.candidates)
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
                session_id=session_id, conversation_id=conversation_id, state=state,
                reply=f"Hi {customer.name.split()[0]}! I can help with a refund. Please send the order ID (like ORD-1001), or just tell me which item it was."
            )

        try:
            order = self._orders.run(state.order_id)
        except OrderLookupError:
            bad_order = state.order_id
            state.order_id, state.reason = None, None
            return self._reply(
                session_id=session_id, conversation_id=conversation_id, state=state,
                reply=f"I couldn't find order {bad_order}. Please check the order ID and send it again."
            )

        if order.customer_id != request.customer_id:
            bad_order = state.order_id
            state.order_id, state.reason = None, None
            return self._reply(
                session_id=session_id, conversation_id=conversation_id, state=state,
                reply=f"Order {bad_order} does not appear to belong to this account. Please send an order ID from your account."
            )

        if not state.reason:
            return self._reply(
                session_id=session_id, conversation_id=conversation_id, state=state,
                reply=f"I found {order.product_name} ({state.order_id}). What is the reason you'd like a refund?"
            )

        refund_request = RefundRequest(
            customer_id=request.customer_id, order_id=state.order_id,
            reason=state.reason, evidence_provided=state.evidence_provided,
        )
        detail = await self._refunds.process_refund(refund_request, db, session_id)
        reply = self._llm.phrase_decision(
            customer.name, detail.decision, order=detail.order,
            reason_codes=detail.reason_codes, rationale=detail.rationale,
        )
        state.refund_runs += 1
        state.last_decision = detail.decision.value
        state.last_order_id = detail.order.order_id if detail.order else state.order_id
        state.order_id, state.reason, state.evidence_provided = None, None, False
        
        return self._reply(
            session_id=session_id, conversation_id=conversation_id, state=state,
            reply=reply, decision=detail.decision, decision_detail=detail,
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
        return f"I found a few orders that could match — which one did you mean? For example: {joined}."

    def _reply(
        self, *, session_id: str, conversation_id: str, state: ChatSessionState,
        reply: str, decision: Any = None, decision_detail: Any = None,
    ) -> ChatResponse:
        """Record an assistant response and build the API response."""
        state.messages.append({"role": "assistant", "content": reply})
        return ChatResponse(
            session_id=session_id, conversation_id=conversation_id,
            reply=reply, decision=decision, decision_detail=decision_detail,
        )

def _normalize_explicit_order_id(order_id: str | None) -> str | None:
    """Normalize an explicit structured order id field."""
    if not order_id:
        return None
    return order_id.strip().upper()
