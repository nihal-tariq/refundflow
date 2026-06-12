"""Unit tests for the deterministic agent tools."""

from __future__ import annotations

from datetime import date

import pytest

from app.tools.customer_lookup import CustomerLookupError, CustomerLookupTool
from app.tools.fraud_checker import FraudCheckTool
from app.tools.order_lookup import OrderLookupError, OrderLookupTool
from app.tools.policy_validator import PolicyValidatorTool

REFERENCE_TODAY = date(2026, 6, 12)


def test_customer_lookup_returns_profile() -> None:
    """A known customer id resolves to a populated profile."""
    profile = CustomerLookupTool().run("CUST-001")
    assert profile.name == "Eleanor Whitfield"
    assert profile.tier == "vip"


def test_customer_lookup_missing_raises() -> None:
    """An unknown customer id raises a lookup error."""
    with pytest.raises(CustomerLookupError):
        CustomerLookupTool().run("CUST-999")


def test_order_lookup_missing_raises() -> None:
    """An unknown order id raises a lookup error."""
    with pytest.raises(OrderLookupError):
        OrderLookupTool().run("ORD-0000")


def test_fraud_band_classification() -> None:
    """High CRM fraud scores classify as the 'high' band."""
    customer = CustomerLookupTool().run("CUST-009")
    result = FraudCheckTool().run(customer)
    assert result.band == "high"
    assert result.risk_score >= result.threshold


def test_policy_flags_digital_product() -> None:
    """A digital order produces a HARD non-refundable violation."""
    customer = CustomerLookupTool().run("CUST-002")
    order = OrderLookupTool().run("ORD-1002")
    result = PolicyValidatorTool(reference_date=REFERENCE_TODAY).run(
        customer, order, reason="changed my mind"
    )
    assert not result.approved
    assert any(v.reason_code == "DIGITAL_NON_REFUNDABLE" for v in result.hard_violations)


def test_policy_window_soft_for_vip() -> None:
    """An out-of-window VIP order is downgraded to a SOFT violation."""
    customer = CustomerLookupTool().run("CUST-007")
    order = OrderLookupTool().run("ORD-1007")
    result = PolicyValidatorTool(reference_date=REFERENCE_TODAY).run(
        customer, order, reason="no longer needed"
    )
    window = [v for v in result.violations if v.reason_code == "WINDOW_EXCEEDED"]
    assert window and window[0].severity == "SOFT"


def test_policy_refund_limit_exceeded() -> None:
    """A repeat refunder trips the 6-month frequency cap (HARD)."""
    customer = CustomerLookupTool().run("CUST-004")
    order = OrderLookupTool().run("ORD-1004")
    result = PolicyValidatorTool(reference_date=REFERENCE_TODAY).run(
        customer, order, reason="changed my mind"
    )
    assert any(v.reason_code == "REFUND_LIMIT_EXCEEDED" for v in result.hard_violations)


def test_policy_clean_customer_approves() -> None:
    """A clean, in-window order yields no violations."""
    customer = CustomerLookupTool().run("CUST-001")
    order = OrderLookupTool().run("ORD-1001")
    result = PolicyValidatorTool(reference_date=REFERENCE_TODAY).run(
        customer, order, reason="defective unit", evidence_provided=True
    )
    assert result.approved
    assert result.violations == []
