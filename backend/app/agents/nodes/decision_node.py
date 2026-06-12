"""Fraud Check → Decision node (terminal routing: Approve / Deny / Escalate)."""

from __future__ import annotations

from typing import Awaitable, Callable

from app.agents.nodes.context import NodeContext
from app.agents.state import AgentState, reasoning_entry
from app.observability.events import EventType
from app.schemas.customer import CustomerProfile
from app.schemas.decision import DecisionType, FraudResult, PolicyResult

NodeFn = Callable[[AgentState], Awaitable[AgentState]]


def make_decision_node(ctx: NodeContext) -> NodeFn:
    """Build the decision node bound to ``ctx``.

    Delegates the actual verdict to :class:`DecisionService` (business logic),
    keeping this node a pure orchestrator. Emits ``escalation_triggered`` when
    routing to human review and always emits ``execution_completed``.
    """

    async def node(state: AgentState) -> AgentState:
        """Compose and emit the terminal decision."""
        await ctx.observer.emit(
            EventType.NODE_ENTERED, node_name="decision",
            message="Composing final decision",
        )

        if state.get("error"):
            decision = DecisionType.ESCALATED
            rationale = (
                "Escalated to human review: required data was missing or invalid "
                f"({state['error']})."
            )
            codes = ["INSUFFICIENT_DATA"]
        else:
            outcome = ctx.decision_service.decide(
                customer=CustomerProfile.model_validate(state["customer_data"]),
                policy=PolicyResult.model_validate(state["policy_result"]),
                fraud=FraudResult.model_validate(state["fraud_result"]),
            )
            decision, rationale, codes = (
                outcome.decision, outcome.rationale, outcome.reason_codes,
            )

        if decision == DecisionType.ESCALATED:
            await ctx.observer.emit(
                EventType.ESCALATION_TRIGGERED, node_name="decision",
                message=rationale, payload={"reason_codes": codes},
            )

        update: AgentState = {
            "current_node": "decision",
            "final_decision": decision.value,
            "decision_rationale": rationale,
            "decision_reason_codes": codes,
            "execution_status": "completed",
            "reasoning_log": state["reasoning_log"]
            + [reasoning_entry("decision", rationale)],
        }
        ctx.observer.snapshot("decision", {**state, **update})
        await ctx.observer.emit(
            EventType.EXECUTION_COMPLETED, node_name="decision",
            message=f"Decision: {decision.value}",
            payload={"decision": decision.value, "reason_codes": codes,
                     "rationale": rationale},
        )
        return update

    return node
