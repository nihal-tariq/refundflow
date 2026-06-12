"""ORM models for agent execution traces (sessions, events, snapshots)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


def _utcnow() -> datetime:
    """Return the current timezone-aware UTC timestamp (testable indirection)."""
    return datetime.now(timezone.utc)


class AgentSession(Base):
    """One end-to-end agent execution for a single refund request."""

    __tablename__ = "agent_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    customer_id: Mapped[str] = mapped_column(String(32), index=True)
    order_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    request_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="running", index=True)
    final_decision: Mapped[str | None] = mapped_column(String(24), nullable=True)
    decision_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    events: Mapped[list["AgentEventRecord"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="AgentEventRecord.id",
    )
    snapshots: Mapped[list["AgentStateSnapshot"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="AgentStateSnapshot.id",
    )


class AgentEventRecord(Base):
    """A single persisted lifecycle event (mirrors :class:`AgentEvent`)."""

    __tablename__ = "agent_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("agent_sessions.session_id"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(40))
    node_name: Mapped[str | None] = mapped_column(String(40), nullable=True)
    tool_name: Mapped[str | None] = mapped_column(String(40), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    session: Mapped[AgentSession] = relationship(back_populates="events")


class AgentStateSnapshot(Base):
    """A durable checkpoint of the LangGraph state after a node executes.

    Complements LangGraph's in-graph checkpointer with a queryable history that
    powers the dashboard's State Inspector and Trace Replay.
    """

    __tablename__ = "agent_state_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("agent_sessions.session_id"), index=True
    )
    graph_node: Mapped[str] = mapped_column(String(40))
    state_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    session: Mapped[AgentSession] = relationship(back_populates="snapshots")


# Composite index to speed the common "events for a session, in order" query.
Index("ix_events_session_created", AgentEventRecord.session_id, AgentEventRecord.id)
