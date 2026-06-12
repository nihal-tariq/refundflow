"""Execution observer — the bridge between the agent and observability.

Nodes call this object to (a) publish live SSE events and (b) persist durable
events and state snapshots. Centralizing it here means the LangGraph nodes never
import the event bus, the DB, or FastAPI — they depend only on this small,
mockable interface (Dependency Inversion).
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from app.config import get_settings
from app.observability.events import AgentEvent, EventType, event_bus
from app.observability.logging import get_logger
from app.repositories.trace_repository import TraceRepository

_logger = get_logger(__name__)


class ExecutionObserver:
    """Publishes + persists agent lifecycle events and state snapshots."""

    def __init__(self, session_id: str, trace_repo: TraceRepository) -> None:
        """Bind the observer to a session and its trace repository."""
        self._session_id = session_id
        self._repo = trace_repo
        self._node_delay = get_settings().node_delay_seconds

    async def emit(
        self,
        event_type: EventType,
        *,
        node_name: str | None = None,
        tool_name: str | None = None,
        message: str | None = None,
        payload: dict[str, Any] | None = None,
        duration_ms: float | None = None,
    ) -> None:
        """Publish an event to subscribers and persist it durably.

        Args:
            event_type: The lifecycle event type.
            node_name: Graph node that produced the event, if any.
            tool_name: Tool involved, if any.
            message: Human-readable summary.
            payload: Structured event data.
            duration_ms: Measured duration for completion events.
        """
        payload = payload or {}
        event = AgentEvent(
            session_id=self._session_id,
            event_type=event_type,
            node_name=node_name,
            tool_name=tool_name,
            message=message,
            payload=payload,
        )
        self._repo.add_event(
            session_id=self._session_id,
            event_type=event_type.value,
            node_name=node_name,
            tool_name=tool_name,
            message=message,
            payload=payload,
            duration_ms=duration_ms,
        )
        await event_bus.publish(event)
        _logger.info(
            "agent_event",
            session_id=self._session_id,
            event_type=event_type.value,
            node=node_name,
            tool=tool_name,
            duration_ms=duration_ms,
        )
        # Demo pacing: briefly yield after entering a node so the SSE stream is
        # visibly animated in the UI. No effect when node_delay_seconds == 0.
        if event_type == EventType.NODE_ENTERED and self._node_delay > 0:
            await asyncio.sleep(self._node_delay)

    def snapshot(self, graph_node: str, state: dict[str, Any]) -> None:
        """Persist a JSON-serializable state snapshot for replay/inspection."""
        self._repo.add_snapshot(self._session_id, graph_node, _scrub(state))

    def timer(self) -> "_Timer":
        """Return a context-manager timer measuring elapsed milliseconds."""
        return _Timer()


class _Timer:
    """Context manager measuring wall-clock duration in milliseconds."""

    def __enter__(self) -> "_Timer":
        """Start the timer."""
        self._start = time.perf_counter()
        return self

    def __exit__(self, *exc: object) -> None:
        """Stop the timer."""
        self.duration_ms = round((time.perf_counter() - self._start) * 1000, 2)


def _scrub(state: dict[str, Any]) -> dict[str, Any]:
    """Return a JSON-safe shallow copy of the state for snapshotting."""
    safe: dict[str, Any] = {}
    for key, value in state.items():
        if isinstance(value, (str, int, float, bool, list, dict)) or value is None:
            safe[key] = value
        else:
            safe[key] = str(value)
    return safe
