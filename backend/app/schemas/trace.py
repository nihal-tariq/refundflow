"""Schemas for execution-trace responses (events, snapshots, history)."""

from __future__ import annotations

from pydantic import BaseModel


class EventSchema(BaseModel):
    """A persisted agent event, as returned by the trace API."""

    event_type: str
    node_name: str | None = None
    tool_name: str | None = None
    message: str | None = None
    payload: dict = {}
    duration_ms: float | None = None
    created_at: str


class SnapshotSchema(BaseModel):
    """A persisted per-node state snapshot."""

    graph_node: str
    state_snapshot: dict
    created_at: str


class SessionSummary(BaseModel):
    """A row in the execution-history list."""

    session_id: str
    customer_id: str
    order_id: str | None = None
    status: str
    final_decision: str | None = None
    created_at: str
    completed_at: str | None = None


class TraceResponse(BaseModel):
    """Full trace for one session: summary + events + snapshots (for replay)."""

    session: SessionSummary
    events: list[EventSchema]
    snapshots: list[SnapshotSchema]
