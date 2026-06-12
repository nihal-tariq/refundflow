"""Agent tools — the deterministic instruments the LangGraph agent calls.

Each tool is a small class with a typed, independently-testable ``run`` method
*and* an ``as_tool()`` adapter exposing it as a LangChain ``StructuredTool``.
Keeping the logic in a class (not a bare ``@tool`` function) lets us inject
repositories (dependency injection) and unit-test the logic without LangChain.

Crucially, **the refund decision is computed by these tools + the decision
service, never by the LLM** — that is what makes adjudication deterministic and
auditable.
"""

from app.tools.customer_lookup import CustomerLookupTool
from app.tools.fraud_checker import FraudCheckTool
from app.tools.order_lookup import OrderLookupTool
from app.tools.policy_validator import PolicyValidatorTool

__all__ = [
    "CustomerLookupTool",
    "OrderLookupTool",
    "PolicyValidatorTool",
    "FraudCheckTool",
]
