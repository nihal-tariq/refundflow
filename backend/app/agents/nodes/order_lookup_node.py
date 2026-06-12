"""Customer Lookup → Order Lookup node."""

from __future__ import annotations

from typing import Awaitable, Callable

from app.agents.nodes.context import NodeContext
from app.agents.state import AgentState, reasoning_entry
from app.observability.events import EventType
from app.tools.order_lookup import OrderLookupError

NodeFn = Callable[[AgentState], Awaitable[AgentState]]


def make_order_lookup_node(ctx: NodeContext) -> NodeFn:
    """Build the order-lookup node bound to ``ctx``.

    Skips work (pass-through) when an upstream error is already present so the
    graph degrades gracefully toward escalation.
    """

    async def node(state: AgentState) -> AgentState:
        """Resolve the order and update state."""
        if state.get("error"):
            return {}
        await ctx.observer.emit(
            EventType.NODE_ENTERED, node_name="order_lookup",
            message="Resolving order details",
        )
        await ctx.observer.emit(
            EventType.TOOL_CALLED, node_name="order_lookup",
            tool_name="order_lookup", payload={"order_id": state["order_id"]},
        )
        try:
            with ctx.observer.timer() as t:
                order = ctx.order_tool.run(state["order_id"])
            data = order.model_dump()
            await ctx.observer.emit(
                EventType.TOOL_COMPLETED, node_name="order_lookup",
                tool_name="order_lookup", duration_ms=t.duration_ms,
                message=f"{order.product_name} — ${order.amount} on {order.purchase_date}",
                payload=data,
            )
            update: AgentState = {
                "order_data": data,
                "current_node": "order_lookup",
                "reasoning_log": state["reasoning_log"]
                + [reasoning_entry(
                    "order_lookup",
                    f"Order {order.order_id}: {order.product_name} "
                    f"(${order.amount}, {order.product_category}, "
                    f"digital={order.is_digital}, final_sale={order.is_final_sale}).",
                    tool="order_lookup", tool_result=data,
                )],
            }
        except OrderLookupError as exc:
            update = {
                "error": str(exc),
                "current_node": "order_lookup",
                "reasoning_log": state["reasoning_log"]
                + [reasoning_entry("order_lookup", f"Lookup failed: {exc}")],
            }
            await ctx.observer.emit(
                EventType.TOOL_COMPLETED, node_name="order_lookup",
                tool_name="order_lookup", message=str(exc), payload={"error": str(exc)},
            )
        ctx.observer.snapshot("order_lookup", {**state, **update})
        return update

    return node
