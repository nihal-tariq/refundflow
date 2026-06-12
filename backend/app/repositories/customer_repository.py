"""Read-only access to the mock CRM customer dataset (``customers.json``)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.config import get_settings
from app.schemas.customer import CustomerProfile


@lru_cache
def _load_customers(path: str) -> dict[str, CustomerProfile]:
    """Load and index customers by id, cached by file path.

    Args:
        path: Absolute path to ``customers.json`` (part of the cache key).

    Returns:
        Mapping of ``customer_id`` to validated :class:`CustomerProfile`.
    """
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return {c["customer_id"]: CustomerProfile.model_validate(c) for c in raw}


class CustomerRepository:
    """Repository exposing customer lookups over the cached CRM dataset."""

    def __init__(self, data_dir: Path | None = None) -> None:
        """Bind the repository to a data directory (defaults to settings)."""
        self._path = str((data_dir or get_settings().data_dir) / "customers.json")

    def get(self, customer_id: str) -> CustomerProfile | None:
        """Return the profile for ``customer_id`` or ``None`` if absent."""
        return _load_customers(self._path).get(customer_id)

    def list_all(self) -> list[CustomerProfile]:
        """Return every customer profile (used for demo pickers)."""
        return list(_load_customers(self._path).values())
