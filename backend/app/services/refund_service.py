"""Refund service — orchestrates a full agent execution for a refund request.

Owns the lifecycle: create the session record, run the agent, persist the final
decision, and assemble the API response from the terminal state. Routes call this
and nothing else; all coordination lives here.
"""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from app.agents.refund_agent import RefundAgent
from app.agents.state import AgentState
from app.observability.logging import bind_context, get_logger
from app.repositories.trace_repository import TraceRepository
from app.schemas.customer import CustomerProfile, OrderInfo
from app.schemas.decision import DecisionType, FraudResult, PolicyResult
from app.schemas.refund import (
    RefundDecisionResponse,
    RefundRequest,
    ReasoningStep,
)

_logger = get_logger(__name__)


class RefundService:
    """Coordinates agent execution and response assembly for refunds."""

    def __init__(self, agent: RefundAgent | None = None) -> None:
        """Inject the agent (defaults to a production-wired instance)."""
        self._agent = agent or RefundAgent()

    async def process_refund(
        self, request: RefundRequest, db: Session, session_id: str | None = None
    ) -> RefundDecisionResponse:
        """Run the agent for a refund request and return the decision response.

        Args:
            request: The validated refund request.
            db: An active SQLAlchemy session (per HTTP request).
            session_id: Optional pre-allocated session id (e.g. from chat).

        Returns:
            A fully-populated :class:`RefundDecisionResponse`.
        """
        session_id = session_id or f"sess-{uuid4().hex[:12]}"
        bind_context(session_id=session_id, trace_id=session_id)
        trace_repo = TraceRepository(db)
        trace_repo.create_session(
            session_id=session_id,
            customer_id=request.customer_id,
            order_id=request.order_id,
            request_reason=request.reason,
        )
        _logger.info(
            "refund_request_received",
            session_id=session_id,
            customer_id=request.customer_id,
            order_id=request.order_id,
        )

        final_state = await self._agent.run(
            session_id=session_id,
            customer_id=request.customer_id,
            order_id=request.order_id,
            reason=request.reason,
            trace_repo=trace_repo,
            evidence_provided=request.evidence_provided,
        )

        decision = final_state.get("final_decision") or DecisionType.ESCALATED.value
        rationale = final_state.get("decision_rationale", "")
        trace_repo.complete_session(session_id, decision, rationale)
        _logger.info(
            "refund_decision", session_id=session_id, decision=decision
        )
        return self._assemble_response(session_id, decision, rationale, final_state)

    def _assemble_response(
        self, session_id: str, decision: str, rationale: str, state: AgentState
    ) -> RefundDecisionResponse:
        """Build the API response model from the terminal agent state."""
        customer = (
            CustomerProfile.model_validate(state["customer_data"])
            if state.get("customer_data")
            else None
        )
        order = (
            OrderInfo.model_validate(state["order_data"])
            if state.get("order_data")
            else None
        )
        policy = (
            PolicyResult.model_validate(state["policy_result"])
            if state.get("policy_result")
            else None
        )
        fraud = (
            FraudResult.model_validate(state["fraud_result"])
            if state.get("fraud_result")
            else None
        )
        reasoning = [
            ReasoningStep(
                node=entry["node"],
                thought=entry["thought"],
                tool=entry.get("tool"),
                tool_result=entry.get("tool_result"),
                timestamp=entry["timestamp"],
            )
            for entry in state.get("reasoning_log", [])
        ]
        return RefundDecisionResponse(
            session_id=session_id,
            decision=DecisionType(decision),
            rationale=rationale,
            reason_codes=list(state.get("decision_reason_codes", [])),
            customer=customer,
            order=order,
            policy_result=policy,
            fraud_result=fraud,
            reasoning_log=reasoning,
        )
