"""Order Lookup → Policy Validation node."""

from __future__ import annotations

from typing import Awaitable, Callable

from app.agents.nodes.context import NodeContext
from app.agents.state import AgentState, reasoning_entry
from app.observability.events import EventType
from app.schemas.customer import CustomerProfile, OrderInfo

NodeFn = Callable[[AgentState], Awaitable[AgentState]]


def make_policy_node(ctx: NodeContext) -> NodeFn:
    """Build the policy-validation node bound to ``ctx``.

    Runs all policy rules *except* fraud (R5), which is evaluated in the
    dedicated downstream fraud node and composed by the decision service. Emits a
    ``validation_completed`` event carrying the structured result.
    """

    async def node(state: AgentState) -> AgentState:
        """Validate the request against policy and update state."""
        if state.get("error"):
            return {}
        await ctx.observer.emit(
            EventType.NODE_ENTERED, node_name="policy_validation",
            message="Validating against refund policy",
        )
        await ctx.observer.emit(
            EventType.TOOL_CALLED, node_name="policy_validation",
            tool_name="policy_validator",
        )
        customer = CustomerProfile.model_validate(state["customer_data"])
        order = OrderInfo.model_validate(state["order_data"])
        with ctx.observer.timer() as t:
            result = ctx.policy_tool.run(
                customer=customer,
                order=order,
                reason=state["request_reason"],
                fraud=None,  # fraud (R5) handled by the fraud node + decision service
                evidence_provided=state.get("evidence_provided", False),
            )
        data = result.model_dump()
        summary = (
            "no violations"
            if not result.violations
            else ", ".join(v.reason_code for v in result.violations)
        )
        await ctx.observer.emit(
            EventType.VALIDATION_COMPLETED, node_name="policy_validation",
            tool_name="policy_validator", duration_ms=t.duration_ms,
            message=f"Policy check: {summary}", payload=data,
        )
        update: AgentState = {
            "policy_result": data,
            "current_node": "policy_validation",
            "reasoning_log": state["reasoning_log"]
            + [reasoning_entry(
                "policy_validation",
                f"Policy validation produced {len(result.violations)} signal(s): {summary}.",
                tool="policy_validator", tool_result=data,
            )],
        }
        ctx.observer.snapshot("policy_validation", {**state, **update})
        return update

    return node
