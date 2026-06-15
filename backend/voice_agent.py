"""RefundFlow voice agent — LiveKit-powered, tool-calling refund assistant.

This agent reuses all existing RefundFlow business logic (CustomerLookupTool,
OrderLookupTool, PolicyValidatorTool, FraudCheckTool, DecisionService) as
native LiveKit function tools.  The LLM orchestrates tool calls in a ReAct
loop; the decision is made deterministically by the same code that powers the
text chat — ensuring parity between channels.

Architecture
────────────
  1.  The LiveKit Agent SDK manages STT → LLM → TTS and turn detection.
  2.  Four @function_tool decorated callables wrap the existing tool classes.
  3.  The LLM sees the raw structured output of every tool and decides the
      final outcome, then narrates it via TTS in voice-safe plain text.

Setup (one-time)
────────────────
  pip install "livekit-agents[silero]>=1.0" livekit-plugins-ai-coustics \
              livekit-plugins-turn-detector

  Add to backend/.env:
      LIVEKIT_URL=wss://your-project.livekit.cloud
      LIVEKIT_API_KEY=your_api_key
      LIVEKIT_API_SECRET=your_api_secret

Run
───
  python voice_agent.py start        # connect to LiveKit Cloud
  python voice_agent.py dev          # hot-reload development mode
"""

from __future__ import annotations

import logging
import json
from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    TurnHandlingOptions,
    cli,
    inference,
    room_io,
    function_tool,
)
from livekit.plugins import silero, ai_coustics
from livekit.plugins.turn_detector.multilingual import MultilingualModel

# ── Bootstrap app config so tools and repositories resolve correctly ────────
load_dotenv(".env")  # loads GROQ_API_KEY, DATABASE_URL, etc.

from app.tools import (  # noqa: E402 — must come after load_dotenv
    CustomerLookupTool,
    OrderLookupTool,
    PolicyValidatorTool,
    FraudCheckTool,
)
from app.tools.customer_lookup import CustomerLookupError  # noqa: E402
from app.tools.order_lookup import OrderLookupError  # noqa: E402
from app.services.decision_service import DecisionService  # noqa: E402
from app.schemas.customer import CustomerProfile, OrderInfo  # noqa: E402
from app.schemas.decision import FraudResult  # noqa: E402

logger = logging.getLogger("refundflow.voice_agent")

# ── Singletons shared across calls (stateless tools are cheap) ──────────────
_customer_tool = CustomerLookupTool()
_order_tool = OrderLookupTool()
_policy_tool = PolicyValidatorTool()
_fraud_tool = FraudCheckTool()
_decision_service = DecisionService()


# ── LiveKit function tools ───────────────────────────────────────────────────

@function_tool
def look_up_customer(customer_id: str) -> str:
    """Look up a customer's account details by their customer ID (e.g. CUST-001).

    Returns the customer's name, account tier (standard/vip), fraud risk score,
    and refund history summary.  Call this first to verify the caller.
    """
    try:
        profile = _customer_tool.run(customer_id)
        return json.dumps({
            "found": True,
            "customer_id": profile.customer_id,
            "name": profile.name,
            "tier": profile.tier,
            "account_age_days": profile.account_age_days,
            "fraud_risk_score": profile.fraud_risk_score,
            "refund_history_count": len(profile.refund_history),
        })
    except CustomerLookupError:
        return json.dumps({"found": False, "error": f"No account found for '{customer_id}'."})


@function_tool
def look_up_order(order_id: str) -> str:
    """Look up an order by its order ID (e.g. ORD-1001).

    Returns product name, purchase date, amount, category, and whether the item
    is digital or final-sale.  Call this after confirming the customer's identity.
    """
    try:
        order = _order_tool.run(order_id)
        return json.dumps({
            "found": True,
            "order_id": order.order_id,
            "product_name": order.product_name,
            "purchase_date": order.purchase_date,
            "amount": order.amount,
            "category": order.category,
            "is_digital": order.is_digital,
            "is_final_sale": order.is_final_sale,
            "customer_id": order.customer_id,
        })
    except OrderLookupError:
        return json.dumps({"found": False, "error": f"Order '{order_id}' could not be found."})


@function_tool
def check_refund_eligibility(
    customer_id: str,
    order_id: str,
    reason: str,
    evidence_provided: bool = False,
) -> str:
    """Run the full refund eligibility check for a customer and order.

    Evaluates all policy rules (return window, product type, refund frequency,
    fraud risk, evidence requirements) and returns a structured eligibility
    result with the final decision: APPROVED, DENIED, or ESCALATED.

    Args:
        customer_id: The customer's CRM identifier.
        order_id: The order being claimed for a refund.
        reason: The customer's stated reason for requesting a refund.
        evidence_provided: Whether the customer has attached photographic evidence.
    """
    try:
        customer = _customer_tool.run(customer_id)
        order = _order_tool.run(order_id)
    except (CustomerLookupError, OrderLookupError) as exc:
        return json.dumps({"decision": "ESCALATED", "error": str(exc)})

    fraud_result = _fraud_tool.run(customer)
    policy_result = _policy_tool.run(customer, order, reason, fraud_result, evidence_provided)

    decision = _decision_service.decide(policy_result, fraud_result, customer)

    violations = [
        {"rule": v.rule_id, "code": v.reason_code, "severity": v.severity}
        for v in policy_result.violations
    ]
    return json.dumps({
        "decision": decision.value,
        "policy_approved": policy_result.approved,
        "fraud_band": fraud_result.band,
        "fraud_score": fraud_result.risk_score,
        "violations": violations,
        "product": order.product_name,
        "amount": order.amount,
        "purchase_date": order.purchase_date,
    })


@function_tool
def list_customer_orders(customer_id: str) -> str:
    """List all orders belonging to a customer.

    Useful when the customer says 'my headphones' or 'that jacket I ordered'
    and you need to match their description to an order ID.
    """
    orders = _order_tool.for_customer(customer_id)
    if not orders:
        return json.dumps({"orders": [], "message": "No orders found for this customer."})
    return json.dumps({
        "orders": [
            {
                "order_id": o.order_id,
                "product_name": o.product_name,
                "purchase_date": o.purchase_date,
                "amount": o.amount,
            }
            for o in orders
        ]
    })


# ── Agent definition ─────────────────────────────────────────────────────────

class RefundVoiceAgent(Agent):
    """Voice-enabled refund support agent for RefundFlow.

    Shares the same deterministic tool stack as the text chat.  The LLM
    orchestrates tool calls; the refund decision is produced by policy +
    fraud logic, never invented by the model.
    """

    def __init__(self) -> None:
        super().__init__(
            instructions="""You are Maya, a warm and professional customer support voice agent for RefundFlow, an e-commerce platform.

Your job is to help customers with refund requests by gathering the necessary information and checking their eligibility using the available tools.

## How to handle a refund request

1. Greet the customer and ask how you can help.
2. If they mention a refund, ask for their customer ID (it looks like C-U-S-T dash followed by numbers).
3. Call look_up_customer to verify their account. If not found, apologize and ask them to check their ID.
4. Ask for the order ID they want to refund (it looks like O-R-D dash followed by numbers). If they describe the item instead, call list_customer_orders to find the right order.
5. Ask for the reason they want a refund.
6. Call check_refund_eligibility with all the information you have gathered.
7. Tell the customer the result clearly and empathetically.

## Decision outcomes

- APPROVED: Congratulate the customer. Tell them the refund for the specific product and amount will be credited to their original payment method within five to ten business days.
- DENIED: Be empathetic. Explain in plain language why it was not approved. Offer to connect them with a specialist if they have questions.
- ESCALATED: Reassure the customer. Tell them a specialist will personally review their case within one business day and no action is needed from them.

## Rules

- Always verify the customer ID before looking up orders.
- Never invent order details, refund decisions, amounts, or policies.
- If the customer is frustrated, acknowledge their feelings calmly before proceeding.
- Do not read out raw identifiers or technical fields like fraud scores or rule IDs.
- Keep replies brief: one to three sentences, one question at a time.
- Speak in plain conversational English. No lists, markdown, or acronyms.
- Spell out identifiers letter by letter when confirming them with the customer.""",
            tools=[
                look_up_customer,
                look_up_order,
                list_customer_orders,
                check_refund_eligibility,
            ],
        )

    async def on_enter(self) -> None:
        """Greet the customer when they connect."""
        await self.session.generate_reply(
            instructions=(
                "Greet the customer warmly. Tell them they have reached RefundFlow support "
                "and ask what you can help them with today. Keep it to one or two sentences."
            ),
            allow_interruptions=True,
        )


# ── Server wiring ────────────────────────────────────────────────────────────

server = AgentServer()


def prewarm(proc: JobProcess) -> None:
    """Pre-load the VAD model once per worker process to avoid cold starts."""
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session(agent_name="refundflow-voice")
async def entrypoint(ctx: JobContext) -> None:
    """Main session handler — wires STT / LLM / TTS and starts the agent."""
    session = AgentSession(
        stt=inference.STT(model="deepgram/nova-3", language="en"),
        llm=inference.LLM(
            model="openai/gpt-4o-mini",  # swap for any inference.LLM model
            extra_kwargs={"reasoning_effort": "low"},
        ),
        tts=inference.TTS(
            model="cartesia/sonic-3",
            voice="9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
            language="en",
        ),
        turn_handling=TurnHandlingOptions(
            turn_detection=MultilingualModel(),
        ),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )

    await session.start(
        agent=RefundVoiceAgent(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=ai_coustics.audio_enhancement(
                    model=ai_coustics.EnhancerModel.QUAIL_VF_L,
                ),
            ),
        ),
    )


if __name__ == "__main__":
    cli.run_app(server)
