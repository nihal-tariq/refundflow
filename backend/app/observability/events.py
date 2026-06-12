"""In-process pub/sub event bus powering Server-Sent Events (SSE).

The LangGraph agent publishes :class:`AgentEvent` objects as it executes; HTTP
SSE handlers subscribe per ``session_id`` and forward events to the browser in
real time. This decouples the agent (producer) from the transport (consumer) —
the agent never imports FastAPI, and the route never imports LangGraph.

For a single-process demo an in-memory ``asyncio.Queue`` fan-out is ideal. In a
multi-replica deployment this class is the one seam to swap for Redis pub/sub.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, AsyncIterator
from uuid import uuid4

from pydantic import BaseModel, Field


class EventType(StrEnum):
    """Canonical agent lifecycle event types streamed to the dashboard."""

    EXECUTION_STARTED = "execution_started"
    NODE_ENTERED = "node_entered"
    TOOL_CALLED = "tool_called"
    TOOL_COMPLETED = "tool_completed"
    VALIDATION_COMPLETED = "validation_completed"
    RETRY_ATTEMPT = "retry_attempt"
    ESCALATION_TRIGGERED = "escalation_triggered"
    EXECUTION_COMPLETED = "execution_completed"
    EXECUTION_FAILED = "execution_failed"


class AgentEvent(BaseModel):
    """A single observable event emitted during agent execution.

    Serialized verbatim to SSE clients and persisted to the ``agent_events``
    table for historical replay.
    """

    event_id: str = Field(default_factory=lambda: str(uuid4()))
    session_id: str
    event_type: EventType
    node_name: str | None = None
    tool_name: str | None = None
    message: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# Sentinel pushed onto a subscriber queue to signal end-of-stream.
_STREAM_DONE = object()


class EventBus:
    """Async fan-out bus keyed by ``session_id``.

    Multiple SSE clients may subscribe to the same session; each receives its
    own queue so a slow consumer never blocks the producer or its peers.
    """

    def __init__(self) -> None:
        """Initialize empty subscriber and completion registries."""
        self._subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)
        self._completed: set[str] = set()

    async def publish(self, event: AgentEvent) -> None:
        """Broadcast an event to every subscriber of its session.

        Marks the session complete on terminal event types so that late
        subscribers immediately receive end-of-stream rather than hanging.
        """
        for queue in list(self._subscribers.get(event.session_id, [])):
            await queue.put(event)
        if event.event_type in (
            EventType.EXECUTION_COMPLETED,
            EventType.EXECUTION_FAILED,
        ):
            self._completed.add(event.session_id)
            for queue in list(self._subscribers.get(event.session_id, [])):
                await queue.put(_STREAM_DONE)

    async def subscribe(self, session_id: str) -> AsyncIterator[AgentEvent]:
        """Yield events for ``session_id`` until the execution completes.

        If the session already finished before subscription, the iterator
        terminates immediately. Always unregisters the queue on exit.
        """
        if session_id in self._completed:
            return
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers[session_id].append(queue)
        try:
            while True:
                item = await queue.get()
                if item is _STREAM_DONE:
                    break
                yield item
        finally:
            self._subscribers[session_id].remove(queue)
            if not self._subscribers[session_id]:
                self._subscribers.pop(session_id, None)

    def reset_session(self, session_id: str) -> None:
        """Clear completion state so a session id can be replayed/re-run."""
        self._completed.discard(session_id)


# Process-wide singleton bus.
event_bus = EventBus()
