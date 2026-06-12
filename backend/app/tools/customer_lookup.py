"""Customer Lookup tool — resolves a customer id to a CRM profile."""

from __future__ import annotations

from langchain_core.tools import StructuredTool

from app.repositories.customer_repository import CustomerRepository
from app.schemas.customer import CustomerProfile


class CustomerLookupError(LookupError):
    """Raised when a customer id cannot be resolved."""


class CustomerLookupTool:
    """Resolve a ``customer_id`` to a full :class:`CustomerProfile`."""

    name = "customer_lookup"
    description = "Look up a customer's CRM profile by customer_id."

    def __init__(self, repository: CustomerRepository | None = None) -> None:
        """Inject the customer repository (defaults to a fresh instance)."""
        self._repo = repository or CustomerRepository()

    def run(self, customer_id: str) -> CustomerProfile:
        """Return the profile for ``customer_id``.

        Args:
            customer_id: The CRM customer identifier (e.g. ``"CUST-001"``).

        Returns:
            The resolved :class:`CustomerProfile`.

        Raises:
            CustomerLookupError: If no customer matches the id.
        """
        profile = self._repo.get(customer_id)
        if profile is None:
            raise CustomerLookupError(f"Customer '{customer_id}' not found")
        return profile

    def as_tool(self) -> StructuredTool:
        """Adapt :meth:`run` into a LangChain ``StructuredTool``."""
        return StructuredTool.from_function(
            func=lambda customer_id: self.run(customer_id).model_dump(),
            name=self.name,
            description=self.description,
        )
