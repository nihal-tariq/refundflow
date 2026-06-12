"""Schemas describing CRM entities: customers, orders, refund history."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class RefundHistoryItem(BaseModel):
    """A single historical refund record on a customer profile."""

    order_id: str
    date: str = Field(description="ISO-8601 date the refund was processed.")
    amount: float
    status: str = Field(description="approved | denied")
    reason: str


class CustomerProfile(BaseModel):
    """A CRM customer profile as consumed by tools and the API."""

    model_config = ConfigDict(extra="ignore")

    customer_id: str
    name: str
    email: str
    tier: str = Field(description="vip | standard")
    purchase_history: list[str] = Field(default_factory=list)
    refund_history: list[RefundHistoryItem] = Field(default_factory=list)
    account_age_days: int
    fraud_risk_score: float = Field(ge=0.0, le=1.0)
    lifetime_value: float = 0.0


class OrderInfo(BaseModel):
    """An order record as returned by the order-lookup tool."""

    model_config = ConfigDict(extra="ignore")

    order_id: str
    customer_id: str
    product_name: str
    product_category: str
    is_digital: bool = False
    is_final_sale: bool = False
    purchase_date: str = Field(description="ISO-8601 purchase date.")
    amount: float
    currency: str = "USD"
