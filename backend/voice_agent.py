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


# ── Agent definition ─────────────────────────────────────────────────────────


def _build_instructions(profile: CustomerProfile | None, customer_id: str) -> str:
    """Build Maya's system prompt, pre-bound to the authenticated caller."""
    if profile is not None:
        who = (
            f"You are already speaking with {profile.name} (customer {customer_id}, "
            f"{profile.tier} tier). Their account is already loaded — NEVER ask for a "
            "customer ID, and never call any tool to verify their identity."
        )
    else:
        who = (
            "You could not load this caller's account automatically. Apologize briefly, "
            "tell them a support specialist will follow up, and do not attempt a refund."
        )

    return f"""You are Maya, the voice customer-support agent for RefundFlow, an e-commerce platform.

{who}

## Handling a refund
1. You have already greeted the caller. When they want a refund you need just two things: which order, and why.
2. Ask which order. They can say an order number (like O-R-D dash one-zero-zero-one) or simply describe the item ("my headphones", "the jacket"). If they describe it, call list_my_orders and match it to an order. If more than one order could match, ask which one they mean — never guess.
3. Ask the reason for the refund.
4. Call check_refund_eligibility with the order id and the reason. Never decide the outcome yourself — only the tool decides.
5. Give the result decision-first (see below).

## Stating the outcome — lead with the verdict, no apologetic preamble
- APPROVED: Lead with the good news. "Your refund for <product>, <amount>, is approved — it goes back to your original payment method in five to ten business days."
- DENIED: State it plainly with the plain-language reason. "Your refund for <product> can't be approved because <reason>." Offer to connect them with a specialist if they have questions.
- ESCALATED: "Your refund for <product> needs a specialist to review it." They'll hear back within one business day and nothing is needed from them.

## Rules
- Never invent order details, decisions, amounts, or policies — state only what the tools return.
- Never say the word "fraud" or read out fraud scores, rule IDs, or other internal fields.
- Keep replies short: one or two sentences, one question at a time.
- Speak plain conversational English — no lists, markdown, or acronyms.
- When confirming an order id, spell it out one letter and digit at a time."""


class RefundVoiceAgent(Agent):
    """Voice refund agent, pre-bound to one authenticated caller.

    The caller's identity comes from the LiveKit room name
    (``refundflow-<customer_id>``), so — exactly like the text channel — we never
    ask them to recite their customer ID. The refund decision is produced by the
    same policy + fraud stack as chat, never invented by the model.
    """

    def __init__(self, customer_id: str, profile: CustomerProfile | None) -> None:
        self._customer_id = customer_id
        self._profile = profile
        super().__init__(instructions=_build_instructions(profile, customer_id))

    async def on_enter(self) -> None:
        """Greet the caller by name as soon as they connect."""
        if self._profile is not None:
            instructions = (
                f"Greet {self._profile.name.split()[0]} warmly by first name, say they've "
                "reached RefundFlow support, and ask how you can help today. One or two sentences."
            )
        else:
            instructions = (
                "Greet the caller, say they've reached RefundFlow support, and ask how you "
                "can help today. One or two sentences."
            )
        await self.session.generate_reply(instructions=instructions, allow_interruptions=True)

    # ── tools (the customer is bound from the room, never asked for) ──────────

    @function_tool
    async def list_my_orders(self) -> str:
        """List the caller's orders. Use this when they describe an item
        ("my headphones", "that jacket") instead of giving an order number."""
        orders = _order_tool.for_customer(self._customer_id)
        if not orders:
            return json.dumps({"orders": [], "message": "No orders found on this account."})
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

    @function_tool
    async def look_up_order(self, order_id: str) -> str:
        """Look up one of the caller's orders by its order ID (e.g. ORD-1001):
        product name, purchase date, amount, and category."""
        try:
            order = _order_tool.run(order_id)
        except OrderLookupError:
            return json.dumps({"found": False, "error": f"Order {order_id} could not be found."})
        if order.customer_id != self._customer_id:
            return json.dumps({"found": False, "error": f"Order {order_id} is not on this account."})
        return json.dumps({
            "found": True,
            "order_id": order.order_id,
            "product_name": order.product_name,
            "purchase_date": order.purchase_date,
            "amount": order.amount,
            "category": order.category,
            "is_digital": order.is_digital,
            "is_final_sale": order.is_final_sale,
        })

    @function_tool
    async def check_refund_eligibility(
        self,
        order_id: str,
        reason: str,
        evidence_provided: bool = False,
    ) -> str:
        """Run the full refund check for the caller's order and return the final
        decision (APPROVED, DENIED, or ESCALATED) along with the product and amount.

        Args:
            order_id: The order being claimed for a refund.
            reason: The caller's stated reason for requesting a refund.
            evidence_provided: Whether the caller has photographic evidence.
        """
        try:
            customer = _customer_tool.run(self._customer_id)
            order = _order_tool.run(order_id)
        except (CustomerLookupError, OrderLookupError) as exc:
            return json.dumps({"decision": "ESCALATED", "error": str(exc)})

        if order.customer_id != self._customer_id:
            return json.dumps({
                "decision": "DENIED",
                "error": f"Order {order_id} is not on this account.",
            })

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
            "violations": violations,
            "product": order.product_name,
            "amount": order.amount,
            "purchase_date": order.purchase_date,
        })


# ── Server wiring ────────────────────────────────────────────────────────────

server = AgentServer()


def prewarm(proc: JobProcess) -> None:
    """Pre-load the VAD model once per worker process to avoid cold starts."""
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


def _customer_id_from_room(room_name: str) -> str:
    """Recover the CRM customer id from the room name (``refundflow-<id>``).

    The token endpoint lower-cases the id into the room name, so we upper-case
    it back to match the CRM (e.g. ``refundflow-cust-001`` -> ``CUST-001``).
    """
    prefix = "refundflow-"
    raw = room_name[len(prefix):] if room_name.startswith(prefix) else room_name
    return raw.upper()


@server.rtc_session(agent_name="refundflow-voice")
async def entrypoint(ctx: JobContext) -> None:
    """Main session handler — wires STT / LLM / TTS and starts the agent."""
    customer_id = _customer_id_from_room(ctx.room.name)
    try:
        profile: CustomerProfile | None = _customer_tool.run(customer_id)
        logger.info("voice session bound to %s (%s)", customer_id, profile.name)
    except CustomerLookupError:
        profile = None
        logger.warning(
            "voice session could not resolve customer %s from room %s",
            customer_id,
            ctx.room.name,
        )

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
        agent=RefundVoiceAgent(customer_id=customer_id, profile=profile),
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
