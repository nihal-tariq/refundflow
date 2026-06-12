"""LangGraph construction for the refund workflow.

The graph is a linear state machine with a conditional terminal:

    START → customer_lookup → order_lookup → policy_validation
          → fraud_check → decision → END

The decision node writes ``final_decision`` (APPROVED / DENIED / ESCALATED);
because the three outcomes are recorded in state (not separate sink nodes), the
graph stays simple while the conditional routing is still made explicit for the
dashboard via ``decision_router``. A checkpointer persists state after every node
so executions can be resumed and inspected.
"""

from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.agents.nodes import (
    NodeContext,
    make_customer_lookup_node,
    make_decision_node,
    make_fraud_node,
    make_order_lookup_node,
    make_policy_node,
)
from app.agents.state import AgentState


def build_refund_graph(ctx: NodeContext, checkpointer: MemorySaver | None = None):
    """Compile and return the refund LangGraph.

    Args:
        ctx: The dependency context injected into every node.
        checkpointer: LangGraph checkpointer; defaults to an in-memory saver so
            in-graph state is persisted after each node (durable replay is also
            stored independently in the snapshot table by the observer).

    Returns:
        A compiled LangGraph runnable accepting an :class:`AgentState`.
    """
    graph = StateGraph(AgentState)

    graph.add_node("customer_lookup", make_customer_lookup_node(ctx))
    graph.add_node("order_lookup", make_order_lookup_node(ctx))
    graph.add_node("policy_validation", make_policy_node(ctx))
    graph.add_node("fraud_check", make_fraud_node(ctx))
    graph.add_node("decision", make_decision_node(ctx))

    graph.add_edge(START, "customer_lookup")
    graph.add_edge("customer_lookup", "order_lookup")
    graph.add_edge("order_lookup", "policy_validation")
    graph.add_edge("policy_validation", "fraud_check")
    graph.add_edge("fraud_check", "decision")
    graph.add_edge("decision", END)

    return graph.compile(checkpointer=checkpointer or MemorySaver())
