"""Tests for customer-facing phrasing (template fallback path).

These lock in the core contract: the customer message is warm, concrete, and
**customer-safe** — internal reasoning (rationale text, fraud language, rule
ids) never leaks into chat. The same safe-reason mapping also feeds the LLM
prompt, so the contract holds in both modes.
"""

from __future__ import annotations

from app.config.settings import Settings
from app.schemas.customer import OrderInfo
from app.schemas.decision import DecisionType
from app.services.llm_service import LLMService

_ORDER = OrderInfo(
    order_id="ORD-1001",
    customer_id="CUST-001",
    product_name="Wireless Noise-Cancelling Headphones",
    product_category="electronics",
    purchase_date="2026-05-28",
    amount=349.99,
)


def make_service() -> LLMService:
    """An LLMService with no client (template mode), isolated from .env."""
    return LLMService(settings=Settings(_env_file=None, llm_provider="anthropic"))


def test_approved_mentions_product_and_amount() -> None:
    """Approval names the product, the amount, and the payout window."""
    reply = make_service().phrase_decision(
        "Eleanor Whitfield", DecisionType.APPROVED, order=_ORDER
    )
    assert "Eleanor" in reply
    assert "Wireless Noise-Cancelling Headphones" in reply
    assert "$349.99" in reply
    assert "5-10 business days" in reply


def test_denied_digital_uses_safe_reason() -> None:
    """A digital-product denial states the policy reason in plain language."""
    reply = make_service().phrase_decision(
        "Marcus Bellamy",
        DecisionType.DENIED,
        order=_ORDER,
        reason_codes=["DIGITAL_NON_REFUNDABLE"],
        rationale="R3 DIGITAL_NON_REFUNDABLE hard violation",
    )
    assert "digital products are non-refundable" in reply
    assert "R3" not in reply  # rule ids never reach the customer


def test_denied_fraud_never_says_fraud() -> None:
    """A fraud denial is phrased as a verification issue, never 'fraud'."""
    reply = make_service().phrase_decision(
        "Viktor Sorokin",
        DecisionType.DENIED,
        order=_ORDER,
        reason_codes=["FRAUD_THRESHOLD"],
        rationale="Fraud score 0.86 >= threshold 0.7.",
    )
    assert "fraud" not in reply.lower()
    assert "0.86" not in reply
    assert "verified" in reply.lower() or "verification" in reply.lower()


def test_escalated_mentions_specialist_and_evidence_hint() -> None:
    """Escalation promises a human follow-up; evidence requests add a hint."""
    reply = make_service().phrase_decision(
        "Harold Pemberton",
        DecisionType.ESCALATED,
        order=_ORDER,
        reason_codes=["EVIDENCE_REQUIRED"],
    )
    assert "specialist" in reply.lower()
    assert "photo" in reply.lower()
    assert "business day" in reply.lower()
