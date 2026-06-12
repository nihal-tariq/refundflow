"""High-level facade over the refund LangGraph.

``RefundAgent`` owns tool construction and graph compilation, and exposes a
single ``run`` coroutine. The service layer calls it; nothing above this class
needs to know about LangGraph internals. A LangGraph ``MemorySaver`` checkpointer
is created per run keyed by ``session_id`` (the graph thread), giving in-graph
checkpointing on top of the durable snapshot table.
"""

from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver

from app.agents.graph import build_refund_graph
from app.agents.nodes import NodeContext
from app.agents.state import AgentState, new_state
from app.observability.events import EventType
from app.observability.logging import get_logger
from app.repositories.trace_repository import TraceRepository
from app.services.decision_service import DecisionService
from app.services.observer import ExecutionObserver
from app.tools import (
    CustomerLookupTool,
    FraudCheckTool,
    OrderLookupTool,
    PolicyValidatorTool,
)

_logger = get_logger(__name__)


class RefundAgent:
    """Compiles the refund graph and executes it for a single request."""

    def __init__(
        self,
        customer_tool: CustomerLookupTool | None = None,
        order_tool: OrderLookupTool | None = None,
        policy_tool: PolicyValidatorTool | None = None,
        fraud_tool: FraudCheckTool | None = None,
        decision_service: DecisionService | None = None,
    ) -> None:
        """Inject tools and services (defaults wire production instances)."""
        self._customer_tool = customer_tool or CustomerLookupTool()
        self._order_tool = order_tool or OrderLookupTool()
        self._policy_tool = policy_tool or PolicyValidatorTool()
        self._fraud_tool = fraud_tool or FraudCheckTool()
        self._decision_service = decision_service or DecisionService()
        # One checkpointer instance; threads are isolated by session_id.
        self._checkpointer = MemorySaver()

    async def run(
        self,
        session_id: str,
        customer_id: str,
        order_id: str,
        reason: str,
        trace_repo: TraceRepository,
        evidence_provided: bool = False,
    ) -> AgentState:
        """Execute the refund workflow and return the final agent state.

        Args:
            session_id: Correlation id (also the LangGraph checkpoint thread).
            customer_id: CRM customer id.
            order_id: Order id under refund.
            reason: Customer's stated reason.
            trace_repo: Per-request repository used by the observer to persist
                events and snapshots.
            evidence_provided: Whether evidence was attached.

        Returns:
            The terminal :class:`AgentState` including ``final_decision``.
        """
        observer = ExecutionObserver(session_id, trace_repo)
        ctx = NodeContext(
            observer=observer,
            customer_tool=self._customer_tool,
            order_tool=self._order_tool,
            policy_tool=self._policy_tool,
            fraud_tool=self._fraud_tool,
            decision_service=self._decision_service,
        )
        graph = build_refund_graph(ctx, checkpointer=self._checkpointer)

        state = new_state(session_id, customer_id, order_id, reason, evidence_provided)
        await observer.emit(
            EventType.EXECUTION_STARTED,
            message=f"Refund workflow started for {customer_id} / {order_id}",
            payload={"customer_id": customer_id, "order_id": order_id},
        )
        try:
            final_state: AgentState = await graph.ainvoke(
                state, config={"configurable": {"thread_id": session_id}}
            )
            return final_state
        except Exception as exc:  # pragma: no cover - defensive guard
            _logger.error("agent_execution_failed", session_id=session_id, error=str(exc))
            await observer.emit(
                EventType.EXECUTION_FAILED, message=f"Execution failed: {exc}",
                payload={"error": str(exc)},
            )
            raise

    def get_state(self, session_id: str) -> AgentState | None:
        """Return the latest checkpointed graph state for a session, if any.

        Reads from the LangGraph checkpointer (in-graph state), enabling
        inspection/resume of the current graph position.
        """
        snapshot = self._checkpointer.get(
            {"configurable": {"thread_id": session_id}}
        )
        return snapshot["channel_values"] if snapshot else None
