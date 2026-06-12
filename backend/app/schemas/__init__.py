"""Pydantic request/response contracts shared across the API and services.

Schemas are the typed boundary of the application. Routes accept and return only
these models, which keeps validation declarative and the OpenAPI schema rich.
"""

from app.schemas.customer import (
    CustomerProfile,
    OrderInfo,
    RefundHistoryItem,
)
from app.schemas.decision import (
    DecisionType,
    FraudResult,
    PolicyResult,
    PolicyViolation,
)
from app.schemas.refund import (
    ChatRequest,
    ChatResponse,
    RefundRequest,
    RefundDecisionResponse,
)
from app.schemas.trace import (
    EventSchema,
    SessionSummary,
    SnapshotSchema,
    TraceResponse,
)

__all__ = [
    "CustomerProfile",
    "OrderInfo",
    "RefundHistoryItem",
    "DecisionType",
    "FraudResult",
    "PolicyResult",
    "PolicyViolation",
    "ChatRequest",
    "ChatResponse",
    "RefundRequest",
    "RefundDecisionResponse",
    "EventSchema",
    "SessionSummary",
    "SnapshotSchema",
    "TraceResponse",
]
