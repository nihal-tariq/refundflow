"""Persistence for agent execution traces (sessions, events, snapshots).

This repository owns all ORM access for the observability tables. Services call
it to record runs and the trace API calls it to read them back for replay.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.trace import AgentEventRecord, AgentSession, AgentStateSnapshot


class TraceRepository:
    """CRUD operations for the execution-trace tables."""

    def __init__(self, db: Session) -> None:
        """Bind the repository to a SQLAlchemy session (per request)."""
        self._db = db

    # ── Sessions ───────────────────────────────────────────────────────────
    def create_session(
        self,
        session_id: str,
        customer_id: str,
        order_id: str | None,
        request_reason: str | None,
    ) -> AgentSession:
        """Insert a new running session row and return it."""
        row = AgentSession(
            session_id=session_id,
            customer_id=customer_id,
            order_id=order_id,
            request_reason=request_reason,
            status="running",
        )
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return row

    def complete_session(
        self, session_id: str, decision: str, rationale: str, status: str = "completed"
    ) -> None:
        """Finalize a session with its decision, rationale, and status."""
        row = self._db.scalar(
            select(AgentSession).where(AgentSession.session_id == session_id)
        )
        if row is None:
            return
        row.final_decision = decision
        row.decision_rationale = rationale
        row.status = status
        row.completed_at = datetime.now(timezone.utc)
        self._db.commit()

    def get_session(self, session_id: str) -> AgentSession | None:
        """Return one session by id (or ``None``)."""
        return self._db.scalar(
            select(AgentSession).where(AgentSession.session_id == session_id)
        )

    def list_sessions(self, limit: int = 50) -> list[AgentSession]:
        """Return the most recent sessions, newest first."""
        return list(
            self._db.scalars(
                select(AgentSession).order_by(AgentSession.id.desc()).limit(limit)
            )
        )

    # ── Events & snapshots ──────────────────────────────────────────────────
    def add_event(
        self,
        session_id: str,
        event_type: str,
        node_name: str | None = None,
        tool_name: str | None = None,
        message: str | None = None,
        payload: dict | None = None,
        duration_ms: float | None = None,
    ) -> None:
        """Persist a single lifecycle event."""
        self._db.add(
            AgentEventRecord(
                session_id=session_id,
                event_type=event_type,
                node_name=node_name,
                tool_name=tool_name,
                message=message,
                payload=payload or {},
                duration_ms=duration_ms,
            )
        )
        self._db.commit()

    def add_snapshot(self, session_id: str, graph_node: str, state: dict) -> None:
        """Persist a per-node state snapshot for replay/inspection."""
        self._db.add(
            AgentStateSnapshot(
                session_id=session_id, graph_node=graph_node, state_snapshot=state
            )
        )
        self._db.commit()

    def get_events(self, session_id: str) -> list[AgentEventRecord]:
        """Return all events for a session, in insertion order."""
        return list(
            self._db.scalars(
                select(AgentEventRecord)
                .where(AgentEventRecord.session_id == session_id)
                .order_by(AgentEventRecord.id)
            )
        )

    def get_snapshots(self, session_id: str) -> list[AgentStateSnapshot]:
        """Return all state snapshots for a session, in insertion order."""
        return list(
            self._db.scalars(
                select(AgentStateSnapshot)
                .where(AgentStateSnapshot.session_id == session_id)
                .order_by(AgentStateSnapshot.id)
            )
        )
