"""Customer-facing phrasing layer.

The LLM never decides anything — the verdict comes from deterministic tools.
This service turns a structured decision into a short, warm, **customer-safe**
chat reply. Internal reasoning (policy rule ids, fraud scores, the rationale)
is deliberately kept OUT of the customer message; operators see all of it in
the admin dashboard instead.

The provider is configurable (``LLM_PROVIDER``: Anthropic, OpenAI, Gemini,
Groq, Mistral, Ollama, or any OpenAI-compatible endpoint). When no provider is
configured — or its package is not installed — the service degrades to a
deterministic template responder, so the app runs fully offline.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Iterable, Sequence

from app.config import get_settings
from app.observability.logging import get_logger
from app.schemas.decision import DecisionType
from app.services.llm_providers import build_chat_model

# Filler words ignored when matching a free-text message against product names.
_PRODUCT_STOPWORDS = frozenset(
    {
        "a", "an", "the", "my", "your", "i", "want", "need", "would", "like",
        "to", "for", "of", "refund", "return", "back", "money", "order", "please",
        "get", "this", "that", "it", "is", "was", "and", "on", "me", "can", "you",
    }
)


if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.config.settings import Settings
    from app.schemas.customer import OrderInfo

_logger = get_logger(__name__)

# Customer-safe explanations per policy reason code. These deliberately avoid
# internal language (rule ids, scores, "violations", "fraud") — the customer
# only ever hears a plain-English, non-sensitive reason.
_SAFE_REASONS: dict[str, str] = {
    "WINDOW_EXCEEDED": "the order falls outside our 30-day refund window",
    "FINAL_SALE": "the item was purchased as a final-sale item, which is non-refundable",
    "DIGITAL_NON_REFUNDABLE": "digital products are non-refundable once delivered",
    "REFUND_LIMIT_EXCEEDED": (
        "the account has reached the maximum number of refunds allowed within six months"
    ),
    "FRAUD_THRESHOLD": "the request could not be verified by our automated checks",
    "FRAUD_BORDERLINE": "the request needs some additional verification on our side",
    "EVIDENCE_REQUIRED": "a photo of the issue is needed to process a damage claim",
    "INSUFFICIENT_DATA": "the order details could not be fully matched to the account",
}

_DEFAULT_REASON: dict[DecisionType, str] = {
    DecisionType.APPROVED: "everything checked out against our refund policy",
    DecisionType.DENIED: "the request did not meet our refund policy",
    DecisionType.ESCALATED: "the request needs a closer look from our team",
}


def _safe_reason(decision: DecisionType, reason_codes: Sequence[str]) -> str:
    """Map internal reason codes to a single customer-safe explanation."""
    phrases = [_SAFE_REASONS[c] for c in reason_codes if c in _SAFE_REASONS]
    if not phrases:
        return _DEFAULT_REASON[decision]
    if len(phrases) == 1:
        return phrases[0]
    return f"{phrases[0]}, and {phrases[1]}"


def _extract_json(raw: str) -> dict | None:
    """Parse the first JSON object out of an LLM response, tolerating prose/fences."""
    if not raw:
        return None
    try:
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            return None
        parsed = json.loads(raw[start : end + 1])
        return parsed if isinstance(parsed, dict) else None
    except (json.JSONDecodeError, ValueError):
        return None


def _tokens(value: str) -> list[str]:
    """Return lowercase alphanumeric tokens without using pattern matching."""
    tokens: list[str] = []
    current: list[str] = []
    for char in value.lower():
        if char.isalnum():
            current.append(char)
        elif current:
            tokens.append("".join(current))
            current = []
    if current:
        tokens.append("".join(current))
    return tokens


def _fallback_intent(message: str) -> str:
    """Small fallback used only when no LLM client is available."""
    normalized = " ".join(_tokens(message))
    if normalized in {"hi", "hello", "hey", "good morning", "good afternoon"}:
        return "GREETING"
    if normalized in {"thanks", "thank you", "thx", "ty", "appreciate it", "much appreciated"}:
        return "GRATITUDE"
    if any(word in normalized.split() for word in ("refund", "return", "exchange")):
        return "REFUND_REQUEST"
    if "money back" in normalized:
        return "REFUND_REQUEST"
    return "OTHER"


def _clean_order_id(value: object, valid: dict[str, "OrderInfo"]) -> str | None:
    """Return ``value`` as a real order id from ``valid``, else ``None``.

    Boxes the LLM: only ids that actually belong to the customer survive, so a
    hallucinated or mistyped id is dropped rather than acted on.
    """
    if not isinstance(value, str):
        return None
    return value.strip().upper() if value.strip().upper() in valid else None


def _normalize_order_id_like(value: object) -> str | None:
    """Normalize an LLM-extracted order id without validating ownership."""
    if not isinstance(value, str):
        return None
    raw = value.strip().upper().replace(" ", "").replace("_", "-")
    if not raw:
        return None
    if raw.startswith("#"):
        raw = raw[1:]
    if raw.startswith("ORDER-"):
        raw = raw.removeprefix("ORDER-")
    if raw.startswith("ORDER"):
        raw = raw.removeprefix("ORDER")
    if raw.startswith("ORD-"):
        suffix = raw.removeprefix("ORD-")
    elif raw.startswith("ORD"):
        suffix = raw.removeprefix("ORD")
    else:
        suffix = raw
    suffix = suffix.strip("-")
    if suffix.isdigit():
        return f"ORD-{suffix.lstrip('0') or '0'}"
    return raw if raw.startswith("ORD-") else None


def _content_to_text(content: object) -> str:
    """Normalize an LLM response ``content`` (str or content blocks) to text."""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "".join(parts).strip()
    return str(content).strip()


@dataclass
class OrderResolution:
    """Outcome of resolving a free-text message to one of a customer's orders.

    Exactly one of these shapes holds:
    - ``order_id`` set            → a single confident match; proceed.
    - ``candidates`` non-empty    → ambiguous; ask the customer to pick.
    - both empty                  → no order referenced / nothing matched.

    ``reason`` carries the refund reason when the customer stated one in the
    same message (e.g. "return my headphones, they're broken").
    ``mentioned_order_id`` preserves a specific order id the user mentioned
    even when it is not one of the current customer's orders, so the caller can
    verify it with the order lookup tool and return a useful account-mismatch or
    not-found response.
    """

    order_id: str | None = None
    candidates: list[str] = field(default_factory=list)
    reason: str | None = None
    mentioned_order_id: str | None = None


class LLMService:
    """Phrases agent decisions for the customer, via LLM or template fallback."""

    def __init__(self, settings: "Settings | None" = None) -> None:
        """Prepare the optional chat client for the configured provider.

        Args:
            settings: Optional settings override (for testing). Defaults to the
                cached application settings.
        """
        self._settings = settings or get_settings()
        self._client = build_chat_model(self._settings)
        # Lazy import: the agents package imports the services package, so a
        # top-level import here would create a cycle. Built once per service so
        # its checkpointer retains conversation memory across turns.
        if self._client is not None:
            from app.agents.chat_graph import ConversationEngine

            self._conversation = ConversationEngine(self._client)
        else:
            self._conversation = None

    @property
    def active(self) -> bool:
        """Whether a live LLM client is configured (vs. template fallback)."""
        return self._client is not None

    @property
    def provider(self) -> str:
        """The configured LLM provider id (e.g. ``groq``)."""
        return self._settings.llm_provider

    @property
    def model(self) -> str:
        """The configured LLM model id (e.g. ``llama-3.3-70b-versatile``)."""
        return self._settings.llm_model

    def classify_intent(self, message: str) -> str:
        """Classify user intent / sentiment using LLM with fallback to heuristics."""
        if self._client is None:
            return _fallback_intent(message)
        try:
            prompt = (
                "You are an intent and sentiment classifier for an e-commerce customer support chatbot.\n"
                "Classify the following user message into exactly one of these categories:\n"
                "- GREETING: Hello, hi, hey, good morning, etc.\n"
                "- GRATITUDE: Thank you, thanks, appreciate it, okay that works, perfect, ty, etc.\n"
                "- FRUSTRATION: Expressions of anger, frustration, disappointment, or abusive language (e.g. damn it, fuck you, this sucks, no way, customer service is terrible, etc.).\n"
                "- REFUND_REQUEST: Requesting a refund, return, or asking about returning a product.\n"
                "- OTHER: Any other general query or statement.\n\n"
                f"User Message: '{message}'\n\n"
                "Respond with ONLY the category name (e.g. GREETING, GRATITUDE, FRUSTRATION, REFUND_REQUEST, OTHER) and nothing else."
            )
            response = self._client.invoke(prompt)
            result = _content_to_text(response.content).upper().strip()
            for cat in ["GREETING", "GRATITUDE", "FRUSTRATION", "REFUND_REQUEST", "OTHER"]:
                if cat in result:
                    return cat
            return "OTHER"
        except Exception as exc:
            _logger.warning("llm_classification_failed", error=str(exc))
            return _fallback_intent(message)

    def resolve_order(
        self, message: str, orders: "Sequence[OrderInfo]"
    ) -> OrderResolution:
        """Resolve a free-text message to one of ``orders`` and extract the reason.

        Handles both order-number references in any form ("order 1001", "ORD-1001",
        "#1001") and product references ("my headphones", "the keyboard"). The LLM
        may only *select* from the provided orders — every id it returns is
        validated against the real set here, so it cannot invent an order.

        Args:
            message: The customer's free-text turn.
            orders: This customer's orders (resolution never crosses accounts).

        Returns:
            An :class:`OrderResolution`. Falls back to deterministic matching when
            no LLM is configured or the call fails.
        """
        if not orders:
            return OrderResolution()
        valid = {o.order_id.upper(): o for o in orders}
        if self._client is None:
            return self._resolve_order_fallback(message, orders)
        try:
            prompt = self._build_resolution_prompt(message, orders)
            raw = _content_to_text(self._client.invoke(prompt).content)
            data = _extract_json(raw)
            if data is None:
                return self._resolve_order_fallback(message, orders)
            order_id = _clean_order_id(data.get("order_id"), valid)
            mentioned_order_id = _normalize_order_id_like(data.get("mentioned_order_id"))
            candidates = [
                cid
                for cid in (
                    _clean_order_id(c, valid)
                    for c in (data.get("candidate_order_ids") or [])
                )
                if cid
            ]
            reason = data.get("reason")
            reason = reason.strip() if isinstance(reason, str) and reason.strip() else None
            # A confident single match supersedes any candidate list.
            if order_id:
                candidates = []
            return OrderResolution(
                order_id=order_id,
                candidates=candidates,
                reason=reason,
                mentioned_order_id=mentioned_order_id,
            )
        except Exception as exc:  # pragma: no cover - network/parse edge cases
            _logger.warning("llm_resolve_order_failed", error=str(exc))
            return self._resolve_order_fallback(message, orders)

    def _build_resolution_prompt(
        self, message: str, orders: "Sequence[OrderInfo]"
    ) -> str:
        """Build the order-resolution prompt listing only this customer's orders."""
        lines = "\n".join(
            f"- {o.order_id} | {o.product_name} | {o.product_category} | "
            f"{o.purchase_date} | ${o.amount:,.2f}"
            for o in orders
        )
        return (
            "You resolve which of a customer's orders they are referring to in an "
            "e-commerce refund chat, and extract their refund reason if stated.\n\n"
            "Match by order number in ANY form (\"order 1001\", \"ORD-1001\", "
            "\"#1001\", \"1001\") OR by product description (\"my headphones\", "
            "\"the keyboard I bought\").\n\n"
            "The customer's orders:\n"
            f"{lines}\n\n"
            f"Customer message: \"{message}\"\n\n"
            "Respond with ONLY a JSON object (no prose, no code fences):\n"
            '{"order_id": <one matching ORD- id or null>, '
            '"mentioned_order_id": <specific ORD- id mentioned by the user, even '
            'if it is not in the list, else null>, '
            '"candidate_order_ids": [<ids>], '
            '"reason": <the refund reason if stated, else null>}\n\n'
            "Rules:\n"
            "- Use ONLY order ids from the list above. Never invent one.\n"
            "- If the user mentions a specific order number/id, always set "
            "mentioned_order_id normalized as ORD-####, even when it is not in "
            "the customer order list.\n"
            "- Exactly one match → set order_id, leave candidate_order_ids empty.\n"
            "- Several plausible matches → order_id null, list them in candidate_order_ids.\n"
            "- No match → order_id null and candidate_order_ids empty.\n"
        )

    def _resolve_order_fallback(
        self, message: str, orders: "Sequence[OrderInfo]"
    ) -> OrderResolution:
        """Deterministic order resolution used when no LLM is available."""
        valid = {o.order_id.upper(): o for o in orders}
        # 1. Explicit order number in any form.
        for token in _tokens(message):
            mentioned = _normalize_order_id_like(token)
            if token.isdigit():
                candidate = f"ORD-{token.lstrip('0') or '0'}".upper()
                if candidate in valid:
                    return OrderResolution(
                        order_id=candidate, mentioned_order_id=candidate
                    )
            candidate = token.upper()
            if candidate.startswith("ORD") and len(candidate) > 3:
                candidate = f"ORD-{candidate[3:].lstrip('0') or '0'}"
            if candidate in valid:
                return OrderResolution(order_id=candidate, mentioned_order_id=candidate)
            if mentioned and any(char.isdigit() for char in token):
                return OrderResolution(mentioned_order_id=mentioned)
        # 2. Product reference by keyword overlap against name + category.
        tokens = {
            t
            for t in _tokens(message)
            if t not in _PRODUCT_STOPWORDS and len(t) > 2
        }
        matches = [
            o.order_id
            for o in orders
            if tokens
            and tokens & {
                w
                for w in _tokens(f"{o.product_name} {o.product_category}")
                if len(w) > 2
            }
        ]
        if len(matches) == 1:
            return OrderResolution(order_id=matches[0])
        if len(matches) > 1:
            return OrderResolution(candidates=matches)
        return OrderResolution()

    async def converse(
        self,
        *,
        conversation_id: str,
        customer_name: str,
        message: str,
        last_decision: str,
        last_order_id: str | None,
    ) -> str:
        """Carry on the conversation after a refund decision, with full memory.

        Routes the turn through the :class:`ConversationEngine` LangGraph, whose
        checkpointer retains the message history per ``conversation_id`` — so the
        assistant remembers what was said and replies in context (e.g. a real
        goodbye to "bye") instead of replaying the same canned follow-up.
        Degrades to the deterministic template when no LLM is configured.
        """
        if self._conversation is None:
            return self._template_followup(customer_name, last_decision, last_order_id)
        try:
            reply = self._conversation.respond(
                conversation_id,
                message,
                customer_name=customer_name,
                last_decision=last_decision,
                last_order_id=last_order_id,
            )
            return reply or self._template_followup(
                customer_name, last_decision, last_order_id
            )
        except Exception as exc:
            _logger.warning("llm_converse_failed", error=str(exc))
            return self._template_followup(customer_name, last_decision, last_order_id)

    def _template_followup(
        self,
        customer_name: str,
        decision: str,
        order_id: str | None,
    ) -> str:
        """Fallback template for follow-up message when LLM is unavailable."""
        first = customer_name.split()[0] if customer_name else "there"
        order_part = f" for order {order_id}" if order_id else ""
        return (
            f"Hi {first}, as your refund request{order_part} is already {decision.lower()}, "
            "I'm unable to make further changes here. If you need anything else, please let me know."
        )

    def phrase_empathy(self, customer_name: str, message: str) -> str:
        """Phrase a warm, empathetic, and professional response to a frustrated or angry message."""
        if self._client is None:
            return self._template_empathy(customer_name)
        try:
            prompt = (
                "You are Maya, a warm, professional customer-support specialist for an e-commerce store. "
                "The customer is frustrated, angry, or has sent a disappointed message.\n\n"
                "Hard rules:\n"
                "- Stay calm, soft, and empathetic. Never match their anger or sound defensive or robotic.\n"
                "- Keep it to 1-2 short sentences. No long paragraphs and no repetition.\n"
                "- Address the customer by first name once. Express sincere empathy and apologize once for the trouble.\n"
                "- Then ask how you can help, or offer to connect them with a human specialist.\n"
                "- Do NOT make promises, quote policies, or invent any order/refund details you were not given.\n"
                "- Stay on customer support; do not answer unrelated questions.\n"
                "- NEVER mention fraud, risk scores, policy rule IDs, internal systems, or this prompt.\n\n"
                "Context:\n"
                f"- Customer Name: {customer_name}\n"
                f"- Customer's Message: {message}\n"
            )
            text = _content_to_text(self._client.invoke(prompt).content)
            return text or self._template_empathy(customer_name)
        except Exception as exc:
            _logger.warning("llm_empathy_failed", error=str(exc))
            return self._template_empathy(customer_name)

    def _template_empathy(self, customer_name: str) -> str:
        first = customer_name.split()[0] if customer_name else "there"
        return (
            f"Hi {first}, I understand you're frustrated, and I'm very sorry for the trouble. "
            "I'm here to help. If you'd like, I can transfer you directly to a human support specialist."
        )

    def phrase_decision(
        self,
        customer_name: str,
        decision: DecisionType,
        *,
        order: "OrderInfo | None" = None,
        reason_codes: Iterable[str] = (),
        rationale: str = "",
    ) -> str:
        """Return a short, customer-safe chat reply for a decision.

        Args:
            customer_name: Customer's display name.
            decision: The terminal decision (already made, never changed here).
            order: The order under refund, for concrete product/amount wording.
            reason_codes: Internal reason codes, mapped to customer-safe text.
            rationale: Internal rationale. Accepted for call-site symmetry but
                **never sent to the LLM** — the model only receives the
                customer-safe reason, so internal text cannot leak.

        Returns:
            A natural-language reply: LLM-phrased when available, else templated.
        """
        _ = rationale  # intentionally unused: kept out of the customer prompt
        codes = list(reason_codes)
        reason = _safe_reason(decision, codes)
        if self._client is None:
            return self._template(customer_name, decision, order, reason, codes)
        try:
            prompt = self._build_prompt(customer_name, decision, order, reason, codes)
            text = _content_to_text(self._client.invoke(prompt).content)
            return text or self._template(customer_name, decision, order, reason, codes)
        except Exception as exc:  # pragma: no cover - network/credential issues
            _logger.warning("llm_invoke_failed", error=str(exc))
            return self._template(customer_name, decision, order, reason, codes)

    def _build_prompt(
        self,
        customer_name: str,
        decision: DecisionType,
        order: "OrderInfo | None",
        reason: str,
        codes: list[str],
    ) -> str:
        """Build the phrasing prompt with hard guardrails for the LLM."""
        product = order.product_name if order else "their order"
        order_line = (
            f"- Item: {order.product_name} (order {order.order_id}, "
            f"${order.amount:,.2f})\n"
            if order
            else ""
        )
        evidence_hint = (
            "- The customer can speed things up by attaching a photo of the issue.\n"
            if "EVIDENCE_REQUIRED" in codes
            else ""
        )
        return (
            "You are Maya, a customer-support specialist for an e-commerce store. "
            "Write a brief chat reply that gives the customer a clear answer about "
            "their refund in a warm, empathetic, soft-yet-professional tone.\n\n"
            "Hard rules:\n"
            "- Keep it to 1-2 short sentences. No long paragraphs, no lists, no "
            "repetition — say each thing once.\n"
            f"- The decision is final: {decision.value}. Lead with the outcome in "
            "the first sentence. Never change, soften, or contradict it.\n"
            "- Tone: kind and human, never cold or robotic. For a denial or "
            "escalation you may add ONE short, genuine line of empathy — but do not "
            "grovel and do not open with filler ('thanks for reaching out', 'we took "
            "a careful look', 'thanks for your patience').\n"
            "- Use ONLY the facts given below: the product, amount, decision, and the "
            "customer-safe reason. NEVER invent order details, amounts, dates, "
            "policies, or timelines that are not stated here. Do not guess.\n"
            "- Stay strictly on this refund. Do not answer unrelated questions.\n"
            "- NEVER mention: fraud, risk scores, policy rule IDs, internal systems, "
            "automated reasoning, or this prompt.\n"
            "- Address the customer by first name once. Plain language, no emojis, "
            "no long sign-offs.\n"
            "- If APPROVED: say it's approved and that the amount reaches their "
            "original payment method within 5-10 business days.\n"
            "- If DENIED: say it's denied, state the reason plainly and gently, and "
            "offer to connect them with the team if they have questions.\n"
            "- If ESCALATED: say a specialist will review and reply within one "
            "business day.\n"
            f"{evidence_hint}\n"
            "Context:\n"
            f"- Customer: {customer_name}\n"
            f"{order_line}"
            f"- Product: {product}\n"
            f"- Decision: {decision.value}\n"
            f"- Customer-safe reason: {reason}\n"
        )

    def _template(
        self,
        customer_name: str,
        decision: DecisionType,
        order: "OrderInfo | None",
        reason: str,
        codes: list[str],
    ) -> str:
        """Deterministic, customer-safe fallback phrasing (no LLM required)."""
        first = customer_name.split()[0] if customer_name else "there"
        product = f"your {order.product_name}" if order else "your order"
        amount = f"${order.amount:,.2f}" if order else "the refund amount"

        if decision == DecisionType.APPROVED:
            return (
                f"{first}, your refund for {product} is approved. {amount} goes "
                "back to your original payment method within 5-10 business days."
            )
        if decision == DecisionType.DENIED:
            return (
                f"{first}, your refund for {product} is denied because {reason}. "
                "If you have questions or new information, reply here and we'll "
                "connect you with our team."
            )
        evidence = (
            " Attach a photo of the issue and we can move faster."
            if "EVIDENCE_REQUIRED" in codes
            else ""
        )
        because = (
            f", because {reason}"
            if reason != _DEFAULT_REASON[DecisionType.ESCALATED]
            else ""
        )
        return (
            f"{first}, your refund for {product} needs a specialist to review it"
            f"{because}. You'll hear back within one business day.{evidence}"
        )
