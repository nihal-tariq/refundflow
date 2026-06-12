"""Data-access layer (Repository pattern).

Repositories are the *only* code that touches a data source. Services depend on
them through their public methods, never on raw JSON files or ORM queries, which
keeps business logic ignorant of storage and trivially mockable in tests.
"""

from app.repositories.customer_repository import CustomerRepository
from app.repositories.order_repository import OrderRepository
from app.repositories.policy_repository import PolicyRepository
from app.repositories.trace_repository import TraceRepository

__all__ = [
    "CustomerRepository",
    "OrderRepository",
    "PolicyRepository",
    "TraceRepository",
]
