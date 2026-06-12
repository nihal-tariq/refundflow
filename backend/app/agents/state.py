"""The LangGraph agent state.

A ``TypedDict`` is used (rather than a Pydantic model) because LangGraph merges
partial state dicts returned by each node, and ``TypedDict`` is the idiomatic,
zero-overhead shape for that. Tool outputs are stored as plain dicts so the whole
state is JSON-serializable for checkpointing and snapshotting.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, TypedDict


class ReasoningEntry(TypedDict):
    """One human-readable reasoning record appended by a node."""

    node: str
    thought: str
    tool: str | None
    tool_result: dict[str, Any] | None
    timestamp: str


class AgentState(TypedDict, total=False):
    """Full state threaded through the refund LangGraph.

    Mirrors the persisted snapshot shape surfaced in the dashboard's State
    Inspector. ``total=False`` lets nodes return partial updates.
    """

    # ── Inputs ──────────────────────────────────────────────────────────────
    session_id: str
    customer_id: str
    order_id: str
    request_reason: str
    evidence_provided: bool

    # ── Tool outputs ────────────────────────────────────────────────────────
    customer_data: dict[str, Any]
    order_data: dict[str, Any]
    policy_result: dict[str, Any]
    fraud_result: dict[str, Any]

    # ── Control / output ────────────────────────────────────────────────────
    current_node: str
    tool_outputs: dict[str, Any]
    reasoning_log: list[ReasoningEntry]
    final_decision: str
    decision_rationale: str
    decision_reason_codes: list[str]
    execution_status: str
    error: str | None
    timestamp: str


def new_state(
    session_id: str,
    customer_id: str,
    order_id: str,
    request_reason: str,
    evidence_provided: bool = False,
) -> AgentState:
    """Construct a fresh :class:`AgentState` for a new execution.

    Args:
        session_id: Unique id correlating events, snapshots, and this run.
        customer_id: The CRM customer id under adjudication.
        order_id: The order being refunded.
        request_reason: The customer's stated reason.
        evidence_provided: Whether evidence was attached.

    Returns:
        An initialized state dict with empty tool outputs and reasoning log.
    """
    return AgentState(
        session_id=session_id,
        customer_id=customer_id,
        order_id=order_id,
        request_reason=request_reason,
        evidence_provided=evidence_provided,
        customer_data={},
        order_data={},
        policy_result={},
        fraud_result={},
        current_node="START",
        tool_outputs={},
        reasoning_log=[],
        final_decision="",
        decision_rationale="",
        execution_status="running",
        error=None,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


def reasoning_entry(
    node: str,
    thought: str,
    tool: str | None = None,
    tool_result: dict[str, Any] | None = None,
) -> ReasoningEntry:
    """Build a timestamped reasoning entry for the reasoning log."""
    return ReasoningEntry(
        node=node,
        thought=thought,
        tool=tool,
        tool_result=tool_result,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
