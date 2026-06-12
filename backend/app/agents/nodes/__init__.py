"""LangGraph node factories.

Each node is produced by a ``make_*_node(ctx)`` factory that captures a shared
:class:`NodeContext` (tools, services, observer). Nodes are thin orchestrators:
they call a tool or service, emit observability events, record a snapshot, and
return a partial state update. No business logic lives here.
"""

from app.agents.nodes.context import NodeContext
from app.agents.nodes.customer_lookup_node import make_customer_lookup_node
from app.agents.nodes.decision_node import make_decision_node
from app.agents.nodes.fraud_node import make_fraud_node
from app.agents.nodes.order_lookup_node import make_order_lookup_node
from app.agents.nodes.policy_node import make_policy_node

__all__ = [
    "NodeContext",
    "make_customer_lookup_node",
    "make_order_lookup_node",
    "make_policy_node",
    "make_fraud_node",
    "make_decision_node",
]
