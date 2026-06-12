"""Integration tests for the end-to-end LangGraph refund agent."""

from __future__ import annotations

import pytest

from app.agents.refund_agent import RefundAgent
from app.repositories.trace_repository import TraceRepository


@pytest.mark.asyncio
async def test_happy_path_approval(db_session) -> None:
    """A clean VIP, in-window order is approved end-to-end."""
    repo = TraceRepository(db_session)
    repo.create_session("t-approve", "CUST-001", "ORD-1001", "defective")
    state = await RefundAgent().run(
        "t-approve", "CUST-001", "ORD-1001", "defective unit", repo, evidence_provided=True
    )
    assert state["final_decision"] == "APPROVED"
    assert state["reasoning_log"]  # reasoning trail captured


@pytest.mark.asyncio
async def test_denial_on_refund_limit(db_session) -> None:
    """A repeat refunder is denied end-to-end."""
    repo = TraceRepository(db_session)
    repo.create_session("t-deny", "CUST-004", "ORD-1004", "changed mind")
    state = await RefundAgent().run(
        "t-deny", "CUST-004", "ORD-1004", "changed my mind", repo
    )
    assert state["final_decision"] == "DENIED"


@pytest.mark.asyncio
async def test_escalation_on_vip_out_of_window(db_session) -> None:
    """A VIP whose window lapsed is escalated, not auto-denied."""
    repo = TraceRepository(db_session)
    repo.create_session("t-esc", "CUST-007", "ORD-1007", "no longer needed")
    state = await RefundAgent().run(
        "t-esc", "CUST-007", "ORD-1007", "no longer needed", repo
    )
    assert state["final_decision"] == "ESCALATED"


@pytest.mark.asyncio
async def test_events_and_snapshots_persisted(db_session) -> None:
    """Every run persists events and per-node snapshots for replay."""
    repo = TraceRepository(db_session)
    repo.create_session("t-trace", "CUST-001", "ORD-1001", "defective")
    await RefundAgent().run("t-trace", "CUST-001", "ORD-1001", "defective", repo, True)
    assert len(repo.get_events("t-trace")) > 0
    assert {s.graph_node for s in repo.get_snapshots("t-trace")} >= {
        "customer_lookup", "order_lookup", "policy_validation", "fraud_check", "decision",
    }


@pytest.mark.asyncio
async def test_missing_customer_escalates(db_session) -> None:
    """An unknown customer degrades gracefully to escalation."""
    repo = TraceRepository(db_session)
    repo.create_session("t-missing", "CUST-404", "ORD-1001", "x")
    state = await RefundAgent().run("t-missing", "CUST-404", "ORD-1001", "x", repo)
    assert state["final_decision"] == "ESCALATED"
