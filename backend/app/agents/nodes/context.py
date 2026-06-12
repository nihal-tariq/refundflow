"""Shared dependency container passed to every node factory."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.decision_service import DecisionService
from app.services.observer import ExecutionObserver
from app.tools import (
    CustomerLookupTool,
    FraudCheckTool,
    OrderLookupTool,
    PolicyValidatorTool,
)


@dataclass
class NodeContext:
    """Dependencies injected into node factories.

    Bundling the tools, the decision service, and the per-run observer in one
    object keeps node signatures uniform and the graph builder declarative.
    """

    observer: ExecutionObserver
    customer_tool: CustomerLookupTool
    order_tool: OrderLookupTool
    policy_tool: PolicyValidatorTool
    fraud_tool: FraudCheckTool
    decision_service: DecisionService
