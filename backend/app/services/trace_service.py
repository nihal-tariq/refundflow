"""Trace service — reads execution history back for the admin dashboard."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.trace import AgentSession
from app.repositories.trace_repository import TraceRepository
from app.schemas.trace import (
    EventSchema,
    SessionSummary,
    SnapshotSchema,
    TraceResponse,
)


class TraceService:
    """Assembles trace/replay views from persisted execution data."""

    def __init__(self, db: Session) -> None:
        """Bind to a SQLAlchemy session and its trace repository."""
        self._repo = TraceRepository(db)

    def list_sessions(self, limit: int = 50) -> list[SessionSummary]:
        """Return recent execution summaries for the history page."""
        return [self._summary(s) for s in self._repo.list_sessions(limit)]

    def get_trace(self, session_id: str) -> TraceResponse | None:
        """Return the full trace (summary + events + snapshots) for replay."""
        session = self._repo.get_session(session_id)
        if session is None:
            return None
        events = [
            EventSchema(
                event_type=e.event_type,
                node_name=e.node_name,
                tool_name=e.tool_name,
                message=e.message,
                payload=e.payload or {},
                duration_ms=e.duration_ms,
                created_at=e.created_at.isoformat(),
            )
            for e in self._repo.get_events(session_id)
        ]
        snapshots = [
            SnapshotSchema(
                graph_node=s.graph_node,
                state_snapshot=s.state_snapshot or {},
                created_at=s.created_at.isoformat(),
            )
            for s in self._repo.get_snapshots(session_id)
        ]
        return TraceResponse(
            session=self._summary(session), events=events, snapshots=snapshots
        )

    @staticmethod
    def _summary(session: AgentSession) -> SessionSummary:
        """Map an ORM session row to its summary schema."""
        return SessionSummary(
            session_id=session.session_id,
            customer_id=session.customer_id,
            order_id=session.order_id,
            status=session.status,
            final_decision=session.final_decision,
            created_at=session.created_at.isoformat(),
            completed_at=session.completed_at.isoformat()
            if session.completed_at
            else None,
        )
