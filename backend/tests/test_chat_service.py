"""Unit tests for conversational chat behavior."""

from __future__ import annotations

import pytest

from app.schemas.decision import DecisionType
from app.schemas.refund import ChatRequest
from app.schemas.refund import RefundDecisionResponse
from app.services.chat_service import ChatService
from app.services.llm_service import LLMService, OrderResolution


class _RefundServiceThatMustNotRun:
    async def process_refund(self, *args, **kwargs):
        raise AssertionError("gratitude should not run the refund agent")


class _UnusedLLMService(LLMService):
    def classify_intent(self, message: str) -> str:
        return "GRATITUDE"

    def phrase_decision(self, *args, **kwargs) -> str:
        raise AssertionError("gratitude should not phrase a decision")


class _FakeRefundService:
    def __init__(self) -> None:
        self.calls = []

    async def process_refund(self, request, db, session_id=None):
        self.calls.append((request, session_id))
        return RefundDecisionResponse(
            session_id=session_id or "sess-test",
            decision=DecisionType.APPROVED,
            rationale="Approved in test.",
            reason_codes=[],
        )


class _FakeLLMService(LLMService):
    def classify_intent(self, message: str) -> str:
        normalized = message.strip().lower()
        if normalized in {"hi", "hello"}:
            return "GREETING"
        if normalized in {"thank you", "thanks"}:
            return "GRATITUDE"
        return "REFUND_REQUEST"

    def resolve_order(self, message, orders) -> OrderResolution:
        normalized = message.lower()
        if "1003" in normalized:
            return OrderResolution(mentioned_order_id="ORD-1003")
        if "1031" in normalized:
            return OrderResolution(order_id="ORD-1031", reason="it is itchy")
        if "1001" in normalized or "headphones" in normalized:
            reason = None
            if "stopped working" in normalized:
                reason = "it stopped working"
            if "broken" in normalized and "headphones" in normalized:
                reason = "they're broken"
            return OrderResolution(order_id="ORD-1001", reason=reason)
        if "apparel" in normalized:
            return OrderResolution(candidates=["ORD-1031", "ORD-1042"])
        return OrderResolution()

    def phrase_decision(self, *args, **kwargs) -> str:
        return "Approved by the test assistant."


@pytest.mark.asyncio
async def test_gratitude_does_not_replay_previous_refund() -> None:
    """A follow-up thank-you is answered conversationally, not adjudicated."""
    service = ChatService(
        refund_service=_RefundServiceThatMustNotRun(),
        llm_service=_UnusedLLMService(),
    )

    response = await service.handle(
        ChatRequest(
            customer_id="CUST-001",
            message="thank you",
            order_id="ORD-1001",
            reason="stale previous refund reason",
        ),
        db=None,
    )

    assert response.decision is None
    assert response.decision_detail is None
    assert "You're welcome" in response.reply


@pytest.mark.asyncio
async def test_chat_collects_order_then_reason_before_running_refund() -> None:
    """The chat service carries refund slots across turns in one conversation."""
    refunds = _FakeRefundService()
    service = ChatService(refund_service=refunds, llm_service=_FakeLLMService())

    first = await service.handle(
        ChatRequest(
            customer_id="CUST-001",
            message="Hi",
            conversation_id="conv-1",
            session_id="turn-1",
        ),
        db=None,
    )
    assert first.decision is None
    assert "order ID" in first.reply

    second = await service.handle(
        ChatRequest(
            customer_id="CUST-001",
            message="ORD-1001",
            conversation_id="conv-1",
            session_id="turn-2",
        ),
        db=None,
    )
    assert second.decision is None
    assert "reason" in second.reply
    assert refunds.calls == []

    final = await service.handle(
        ChatRequest(
            customer_id="CUST-001",
            message="broken",
            conversation_id="conv-1",
            session_id="turn-3",
        ),
        db=None,
    )

    assert final.decision == DecisionType.APPROVED
    assert final.reply == "Approved by the test assistant."
    assert len(refunds.calls) == 1
    request, session_id = refunds.calls[0]
    assert request.order_id == "ORD-1001"
    assert request.reason == "broken"
    assert session_id == "turn-3"
    assert service._sessions["conv-1"].messages[-1]["role"] == "assistant"


@pytest.mark.asyncio
async def test_chat_resolves_order_from_natural_language_number() -> None:
    """"refund for order 1001" resolves the real ORD-id without a fixed format."""
    refunds = _FakeRefundService()
    service = ChatService(refund_service=refunds, llm_service=_FakeLLMService())

    response = await service.handle(
        ChatRequest(
            customer_id="CUST-001",
            message="I need a refund for order 1001, it stopped working",
        ),
        db=None,
    )

    assert response.decision == DecisionType.APPROVED
    assert len(refunds.calls) == 1
    assert refunds.calls[0][0].order_id == "ORD-1001"


@pytest.mark.asyncio
async def test_chat_resolves_order_from_product_reference() -> None:
    """"return my headphones" resolves to the customer's headphones order."""
    refunds = _FakeRefundService()
    service = ChatService(refund_service=refunds, llm_service=_FakeLLMService())

    response = await service.handle(
        ChatRequest(
            customer_id="CUST-001",
            message="I need to return my headphones, they're broken",
        ),
        db=None,
    )

    assert response.decision == DecisionType.APPROVED
    assert refunds.calls[0][0].order_id == "ORD-1001"


@pytest.mark.asyncio
async def test_chat_asks_to_clarify_when_reference_is_ambiguous() -> None:
    """An ambiguous product reference asks the customer to pick, not adjudicates."""
    refunds = _FakeRefundService()
    service = ChatService(refund_service=refunds, llm_service=_FakeLLMService())

    response = await service.handle(
        ChatRequest(
            customer_id="CUST-001",
            message="I'd like to return my apparel item",
        ),
        db=None,
    )

    assert response.decision is None
    assert refunds.calls == []
    assert "which one" in response.reply.lower()


@pytest.mark.asyncio
async def test_switching_customer_resets_old_conversation_state() -> None:
    """Changing customers clears old order slots and last-decision context."""
    refunds = _FakeRefundService()
    service = ChatService(refund_service=refunds, llm_service=_FakeLLMService())

    await service.handle(
        ChatRequest(
            customer_id="CUST-001",
            message="ORD-1001",
            conversation_id="conv-switch",
            session_id="turn-1",
        ),
        db=None,
    )

    response = await service.handle(
        ChatRequest(
            customer_id="CUST-002",
            message="Hi",
            conversation_id="conv-switch",
            session_id="turn-2",
        ),
        db=None,
    )

    state = service._sessions["conv-switch"]
    assert response.decision is None
    assert state.customer_id == "CUST-002"
    assert state.order_id is None
    assert state.reason is None
    assert state.last_decision is None
    assert refunds.calls == []


@pytest.mark.asyncio
async def test_new_refund_after_completed_refund_starts_fresh_flow() -> None:
    """A completed conversation can start another refund instead of looping."""
    refunds = _FakeRefundService()
    service = ChatService(refund_service=refunds, llm_service=_FakeLLMService())

    first = await service.handle(
        ChatRequest(
            customer_id="CUST-001",
            message="I need a refund for order 1001, it stopped working",
            conversation_id="conv-repeat",
            session_id="turn-1",
        ),
        db=None,
    )
    assert first.decision == DecisionType.APPROVED

    second = await service.handle(
        ChatRequest(
            customer_id="CUST-001",
            message="I need another refund for order 1031, it is itchy",
            conversation_id="conv-repeat",
            session_id="turn-2",
        ),
        db=None,
    )

    assert second.decision == DecisionType.APPROVED
    assert len(refunds.calls) == 2
    assert refunds.calls[0][0].order_id == "ORD-1001"
    assert refunds.calls[1][0].order_id == "ORD-1031"
    assert refunds.calls[1][0].reason == "it is itchy"


@pytest.mark.asyncio
async def test_wrong_account_order_id_reports_mismatch_instead_of_looping() -> None:
    """Mentioned order ids outside the active customer are verified and rejected."""
    refunds = _FakeRefundService()
    service = ChatService(refund_service=refunds, llm_service=_FakeLLMService())

    first = await service.handle(
        ChatRequest(
            customer_id="CUST-001",
            message="can i get a refund for order id 1003",
            conversation_id="conv-wrong-account",
            session_id="turn-1",
        ),
        db=None,
    )

    assert first.decision is None
    assert refunds.calls == []
    assert "does not appear to belong to this account" in first.reply

    second = await service.handle(
        ChatRequest(
            customer_id="CUST-001",
            message="1003",
            conversation_id="conv-wrong-account",
            session_id="turn-2",
        ),
        db=None,
    )

    assert second.decision is None
    assert refunds.calls == []
    assert "does not appear to belong to this account" in second.reply
