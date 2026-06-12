"""Execution-trace routes (history list + full trace for replay)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.v1.dependencies import get_trace_service
from app.schemas.trace import SessionSummary, TraceResponse
from app.services.trace_service import TraceService

router = APIRouter(tags=["traces"])


@router.get(
    "/sessions",
    response_model=list[SessionSummary],
    summary="List recent agent executions",
)
def list_sessions(
    limit: int = 50,
    service: TraceService = Depends(get_trace_service),
) -> list[SessionSummary]:
    """Return recent execution summaries for the history page."""
    return service.list_sessions(limit)


@router.get(
    "/logs/{session_id}",
    response_model=TraceResponse,
    summary="Full execution trace for a session (events + snapshots)",
)
def get_trace(
    session_id: str,
    service: TraceService = Depends(get_trace_service),
) -> TraceResponse:
    """Return the full trace for ``session_id`` (used for replay).

    Raises:
        HTTPException: 404 if the session is unknown.
    """
    trace = service.get_trace(session_id)
    if trace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found",
        )
    return trace
