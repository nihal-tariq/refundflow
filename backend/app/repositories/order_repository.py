"""Read-only access to the mock order dataset (``orders.json``)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.config import get_settings
from app.schemas.customer import OrderInfo


@lru_cache
def _load_orders(path: str) -> dict[str, OrderInfo]:
    """Load and index orders by id, cached by file path."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return {o["order_id"]: OrderInfo.model_validate(o) for o in raw}


class OrderRepository:
    """Repository exposing order lookups over the cached order dataset."""

    def __init__(self, data_dir: Path | None = None) -> None:
        """Bind the repository to a data directory (defaults to settings)."""
        self._path = str((data_dir or get_settings().data_dir) / "orders.json")

    def get(self, order_id: str) -> OrderInfo | None:
        """Return the order for ``order_id`` or ``None`` if absent."""
        return _load_orders(self._path).get(order_id)

    def list_for_customer(self, customer_id: str) -> list[OrderInfo]:
        """Return all orders belonging to ``customer_id``."""
        return [o for o in _load_orders(self._path).values() if o.customer_id == customer_id]
