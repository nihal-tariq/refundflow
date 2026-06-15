"""Order Lookup tool — resolves an order id to order details."""

from __future__ import annotations

from langchain_core.tools import StructuredTool

from app.repositories.order_repository import OrderRepository
from app.schemas.customer import OrderInfo


class OrderLookupError(LookupError):
    """Raised when an order id cannot be resolved."""


class OrderLookupTool:
    """Resolve an ``order_id`` to its :class:`OrderInfo` (date, amount, category)."""

    name = "order_lookup"
    description = (
        "Look up an order by order_id: product, purchase date, amount, category."
    )

    def __init__(self, repository: OrderRepository | None = None) -> None:
        """Inject the order repository (defaults to a fresh instance)."""
        self._repo = repository or OrderRepository()

    def run(self, order_id: str) -> OrderInfo:
        """Return order details for ``order_id``.

        Args:
            order_id: The order identifier (e.g. ``"ORD-1001"``).

        Returns:
            The resolved :class:`OrderInfo`.

        Raises:
            OrderLookupError: If no order matches the id.
        """
        order = self._repo.get(order_id)
        if order is None:
            raise OrderLookupError(f"Order '{order_id}' not found")
        return order

    def for_customer(self, customer_id: str) -> list[OrderInfo]:
        """Return every order belonging to ``customer_id`` (may be empty).

        Used by the conversational layer to resolve free-text references like
        "my headphones" against only this customer's own orders.
        """
        return self._repo.list_for_customer(customer_id)

    def as_tool(self) -> StructuredTool:
        """Adapt :meth:`run` into a LangChain ``StructuredTool``."""
        return StructuredTool.from_function(
            func=lambda order_id: self.run(order_id).model_dump(),
            name=self.name,
            description=self.description,
        )
