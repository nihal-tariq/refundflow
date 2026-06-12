"""Unit tests for the decision service (verdict composition)."""

from __future__ import annotations

from app.schemas.customer import CustomerProfile
from app.schemas.decision import (
    DecisionType,
    FraudResult,
    PolicyResult,
    PolicyViolation,
)
from app.services.decision_service import DecisionService

_CUSTOMER = CustomerProfile(
    customer_id="CUST-T",
    name="Test User",
    email="t@example.com",
    tier="vip",
    purchase_history=[],
    refund_history=[],
    account_age_days=900,
    fraud_risk_score=0.1,
    lifetime_value=5000.0,
)
_LOW_FRAUD = FraudResult(risk_score=0.1, band="low", threshold=0.7)


def _policy(*violations: PolicyViolation) -> PolicyResult:
    """Build a policy result; approved iff no HARD violations present."""
    approved = not any(v.severity == "HARD" for v in violations)
    return PolicyResult(approved=approved, violations=list(violations))


def test_clean_request_is_approved() -> None:
    """No violations and low fraud → APPROVED."""
    outcome = DecisionService().decide(_CUSTOMER, _policy(), _LOW_FRAUD)
    assert outcome.decision == DecisionType.APPROVED


def test_hard_violation_is_denied() -> None:
    """A HARD violation → DENIED."""
    hard = PolicyViolation(
        rule_id="R3", reason_code="DIGITAL_NON_REFUNDABLE", severity="HARD",
        message="digital",
    )
    outcome = DecisionService().decide(_CUSTOMER, _policy(hard), _LOW_FRAUD)
    assert outcome.decision == DecisionType.DENIED
    assert "DIGITAL_NON_REFUNDABLE" in outcome.reason_codes


def test_soft_violation_is_escalated() -> None:
    """A SOFT-only signal → ESCALATED with an explanatory rationale."""
    soft = PolicyViolation(
        rule_id="R1", reason_code="WINDOW_EXCEEDED", severity="SOFT",
        message="VIP out of window",
    )
    outcome = DecisionService().decide(_CUSTOMER, _policy(soft), _LOW_FRAUD)
    assert outcome.decision == DecisionType.ESCALATED
    assert "VIP" in outcome.rationale


def test_borderline_fraud_escalates() -> None:
    """A borderline fraud band (no hard violations) → ESCALATED."""
    fraud = FraudResult(risk_score=0.62, band="borderline", threshold=0.7)
    outcome = DecisionService().decide(_CUSTOMER, _policy(), fraud)
    assert outcome.decision == DecisionType.ESCALATED


def test_high_fraud_denies() -> None:
    """A high fraud band → DENIED."""
    fraud = FraudResult(risk_score=0.88, band="high", threshold=0.7)
    outcome = DecisionService().decide(_CUSTOMER, _policy(), fraud)
    assert outcome.decision == DecisionType.DENIED
