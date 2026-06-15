"""START → Customer Lookup node."""

from __future__ import annotations

from typing import Awaitable, Callable

from app.agents.nodes.context import NodeContext
from app.agents.state import AgentState, reasoning_entry
from app.observability.events import EventType
from app.tools.customer_lookup import CustomerLookupError

NodeFn = Callable[[AgentState], Awaitable[AgentState]]


def make_customer_lookup_node(ctx: NodeContext) -> NodeFn:
    """Build the customer-lookup node bound to ``ctx``.

    The node resolves the customer profile via the customer tool, emitting
    ``node_entered`` / ``tool_called`` / ``tool_completed`` events and recording
    a state snapshot. On lookup failure it sets ``error`` and lets the decision
    node escalate (graceful degradation).
    """

    async def node(state: AgentState) -> AgentState:
        """Resolve the customer profile and update state."""
        await ctx.observer.emit(
            EventType.NODE_ENTERED, node_name="customer_lookup",
            message="Resolving customer profile",
        )
        await ctx.observer.emit(
            EventType.TOOL_CALLED, node_name="customer_lookup",
            tool_name="customer_lookup", payload={"customer_id": state["customer_id"]},
        )
        try:
            with ctx.observer.timer() as t:
                profile = ctx.customer_tool.run(state["customer_id"])
            data = profile.model_dump()
            await ctx.observer.emit(
                EventType.TOOL_COMPLETED, node_name="customer_lookup",
                tool_name="customer_lookup", duration_ms=t.duration_ms,
                message=f"Found {profile.name} ({profile.tier})", payload=data,
            )
            update: AgentState = {
                "customer_data": data,
                "current_node": "customer_lookup",
                "reasoning_log": state["reasoning_log"]
                + [reasoning_entry(
                    "customer_lookup",
                    f"Customer {profile.name} resolved — tier={profile.tier}, "
                    f"fraud={profile.fraud_risk_score}, refunds={len(profile.refund_history)}.",
                    tool="customer_lookup", tool_result=data,
                )],
            }

            
        except CustomerLookupError as exc:
            update = _failure(state, str(exc))
            await ctx.observer.emit(
                EventType.TOOL_COMPLETED, node_name="customer_lookup",
                tool_name="customer_lookup", message=str(exc),
                payload={"error": str(exc)},
            )
        ctx.observer.snapshot("customer_lookup", {**state, **update})
        return update

    return node


def _failure(state: AgentState, error: str) -> AgentState:
    """Build a partial state update recording a recoverable lookup error."""
    return {
        "error": error,
        "current_node": "customer_lookup",
        "reasoning_log": state["reasoning_log"]
        + [reasoning_entry("customer_lookup", f"Lookup failed: {error}")],
    }
