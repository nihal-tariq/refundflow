"""Request/response schemas for the refund and chat endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.decision import DecisionType, FraudResult, PolicyResult
from app.schemas.customer import CustomerProfile, OrderInfo


class RefundRequest(BaseModel):
    """Inbound payload to run the refund agent."""

    customer_id: str = Field(examples=["CUST-001"])
    order_id: str = Field(examples=["ORD-1001"])
    product_name: str | None = Field(default=None, examples=["Wireless Headphones"])
    purchase_date: str | None = Field(default=None, examples=["2026-05-28"])
    reason: str = Field(examples=["Item arrived defective"], min_length=1)
    evidence_provided: bool = Field(
        default=False,
        description="Whether the customer attached photographic evidence.",
    )


class ReasoningStep(BaseModel):
    """A single human-readable reasoning entry from the agent."""

    node: str
    thought: str
    tool: str | None = None
    tool_result: dict | None = None
    timestamp: str


class RefundDecisionResponse(BaseModel):
    """The agent's final decision plus the full reasoning trail."""

    session_id: str
    decision: DecisionType
    rationale: str
    reason_codes: list[str] = Field(default_factory=list)
    customer: CustomerProfile | None = None
    order: OrderInfo | None = None
    policy_result: PolicyResult | None = None
    fraud_result: FraudResult | None = None
    reasoning_log: list[ReasoningStep] = Field(default_factory=list)


class ChatRequest(BaseModel):
    """A conversational turn from the customer."""

    customer_id: str = Field(examples=["CUST-001"])
    message: str = Field(min_length=1)
    conversation_id: str | None = Field(
        default=None, description="Stable id for a multi-turn chat conversation."
    )
    session_id: str | None = Field(
        default=None, description="Execution/turn id used for live trace streaming."
    )
    order_id: str | None = None
    reason: str | None = None
    evidence_provided: bool = False


class ChatResponse(BaseModel):
    """The agent's conversational reply, optionally carrying a decision."""

    session_id: str
    conversation_id: str | None = None
    reply: str
    decision: DecisionType | None = None
    decision_detail: RefundDecisionResponse | None = None
    llm_used: bool = Field(
        default=False,
        description="Whether the LLM phrasing layer (not a template) produced this reply.",
    )
