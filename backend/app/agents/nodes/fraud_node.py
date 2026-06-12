"""Policy Validation → Fraud Check node."""

from __future__ import annotations

from typing import Awaitable, Callable

from app.agents.nodes.context import NodeContext
from app.agents.state import AgentState, reasoning_entry
from app.observability.events import EventType
from app.schemas.customer import CustomerProfile

NodeFn = Callable[[AgentState], Awaitable[AgentState]]


def make_fraud_node(ctx: NodeContext) -> NodeFn:
    """Build the fraud-check node bound to ``ctx``.

    Produces the fraud assessment that the decision node composes with the
    policy result. Emits ``tool_called`` / ``tool_completed`` events.
    """

    async def node(state: AgentState) -> AgentState:
        """Run the fraud tool and update state."""
        if state.get("error"):
            return {}
        await ctx.observer.emit(
            EventType.NODE_ENTERED, node_name="fraud_check",
            message="Assessing fraud risk",
        )
        await ctx.observer.emit(
            EventType.TOOL_CALLED, node_name="fraud_check", tool_name="fraud_check",
        )
        customer = CustomerProfile.model_validate(state["customer_data"])
        with ctx.observer.timer() as t:
            result = ctx.fraud_tool.run(customer)
        data = result.model_dump()
        await ctx.observer.emit(
            EventType.TOOL_COMPLETED, node_name="fraud_check", tool_name="fraud_check",
            duration_ms=t.duration_ms,
            message=f"Fraud risk {result.risk_score} ({result.band})", payload=data,
        )
        update: AgentState = {
            "fraud_result": data,
            "current_node": "fraud_check",
            "reasoning_log": state["reasoning_log"]
            + [reasoning_entry(
                "fraud_check",
                f"Fraud assessment: score={result.risk_score}, band={result.band} "
                f"(threshold {result.threshold}).",
                tool="fraud_check", tool_result=data,
            )],
        }
        ctx.observer.snapshot("fraud_check", {**state, **update})
        return update

    return node
