"""Server-Sent Events (SSE) route for real-time agent observability.

Subscribes to the in-process event bus for a ``session_id`` and streams each
:class:`AgentEvent` to the browser as it is emitted by the running graph. SSE is
used (not polling) because the data flow is strictly one-way server→client and
naturally event-shaped.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from app.observability.events import event_bus

router = APIRouter(tags=["events"])


@router.get(
    "/events/{session_id}",
    summary="Live SSE stream of agent events for a session",
)
async def stream_events(session_id: str) -> EventSourceResponse:
    """Stream agent lifecycle events for ``session_id`` over SSE.

    The connection closes automatically when the execution emits a terminal
    event (``execution_completed`` / ``execution_failed``).

    Args:
        session_id: The session to subscribe to.

    Returns:
        An ``EventSourceResponse`` yielding JSON event payloads.
    """

    async def event_generator() -> AsyncIterator[dict]:
        """Yield SSE-formatted events from the bus until the stream ends."""
        async for event in event_bus.subscribe(session_id):
            yield {
                "event": event.event_type.value,
                "data": event.model_dump_json(),
            }

    return EventSourceResponse(event_generator())
