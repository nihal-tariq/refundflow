"""Unit tests for conversational chat behavior."""

from __future__ import annotations

import pytest

from app.schemas.decision import DecisionType
from app.schemas.refund import ChatRequest
from app.schemas.refund import RefundDecisionResponse
from app.services.chat_service import ChatService


class _RefundServiceThatMustNotRun:
    async def process_refund(self, *args, **kwargs):
        raise AssertionError("gratitude should not run the refund agent")


class _UnusedLLMService:
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


class _FakeLLMService:
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
