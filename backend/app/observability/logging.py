"""Structured, OpenTelemetry-inspired logging built on ``structlog``.

Every log line is a JSON object carrying contextual fields (``trace_id``,
``session_id``, ``node``, ``event_type``, ``duration_ms``) so logs can be shipped
to a real observability backend unchanged — and surfaced in the admin dashboard.
Use :func:`bind_context` / :func:`get_logger` rather than the stdlib logger so
context propagates automatically.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

from app.config import get_settings


def configure_logging() -> None:
    """Configure ``structlog`` + stdlib logging once at application startup.

    Renders JSON in production (``LOG_JSON=true``) and a colorized console
    format otherwise. Idempotent — safe to call multiple times.
    """
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    renderer: structlog.types.Processor = (
        structlog.processors.JSONRenderer()
        if settings.log_json
        else structlog.dev.ConsoleRenderer(colors=True)
    )

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)


def get_logger(name: str | None = None, **initial: Any) -> structlog.stdlib.BoundLogger:
    """Return a bound structured logger.

    Args:
        name: Logical logger name (typically the module ``__name__``).
        **initial: Key/value pairs bound to every record from this logger.

    Returns:
        A ``structlog`` bound logger.
    """
    logger = structlog.get_logger(name)
    return logger.bind(**initial) if initial else logger


def bind_context(**kwargs: Any) -> None:
    """Bind context variables (e.g. ``trace_id``) onto the current async task.

    Bound values are merged into every subsequent log line until cleared,
    giving request- and session-scoped correlation without threading args.
    """
    structlog.contextvars.bind_contextvars(**kwargs)


def clear_context() -> None:
    """Clear all context variables bound via :func:`bind_context`."""
    structlog.contextvars.clear_contextvars()
