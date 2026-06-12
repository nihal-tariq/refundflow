"""FastAPI dependency providers (Dependency Injection wiring).

Services are constructed here and injected into routes via ``Depends`` so route
handlers never instantiate their own collaborators. This makes routes trivial to
test (override the dependency) and keeps construction in one place.
"""

from app.api.v1.dependencies.providers import (
    get_chat_service,
    get_customer_repository,
    get_refund_service,
    get_trace_service,
)

__all__ = [
    "get_chat_service",
    "get_refund_service",
    "get_trace_service",
    "get_customer_repository",
]
