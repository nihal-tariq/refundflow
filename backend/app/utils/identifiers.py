"""Identifier helpers."""

from __future__ import annotations

from uuid import uuid4


def new_session_id(prefix: str = "sess") -> str:
    """Return a short, collision-resistant session id.

    Args:
        prefix: Human-readable prefix (default ``"sess"``).

    Returns:
        A string like ``"sess-1a2b3c4d5e6f"``.
    """
    return f"{prefix}-{uuid4().hex[:12]}"
