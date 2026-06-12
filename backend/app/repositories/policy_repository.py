"""Access to the human-authored refund policy document.

The policy *text* lives in ``refund_policy.md`` (the source of truth a human
edits). The validator tool encodes the same rules numerically; this repository
exposes the document so the agent can quote it and the UI can render it.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from app.config import get_settings


@lru_cache
def _read_policy(path: str) -> str:
    """Read the policy markdown, cached by file path."""
    return Path(path).read_text(encoding="utf-8")


class PolicyRepository:
    """Repository exposing the refund policy document."""

    def __init__(self, data_dir: Path | None = None) -> None:
        """Bind the repository to a data directory (defaults to settings)."""
        self._path = str((data_dir or get_settings().data_dir) / "refund_policy.md")

    def get_policy_text(self) -> str:
        """Return the full refund policy markdown."""
        return _read_policy(self._path)
