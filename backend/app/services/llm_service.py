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

from typing import TYPE_CHECKING, Iterable, Sequence

from app.config import get_settings
from app.observability.logging import get_logger
from app.schemas.decision import DecisionType
from app.services.llm_providers import build_chat_model

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
            "You are Maya, a warm, professional customer-support specialist for an "
            "e-commerce store. Write a short chat reply (2-4 sentences) telling the "
            "customer the outcome of their refund request.\n\n"
            "Hard rules:\n"
            f"- The decision is already final: {decision.value}. Never change, "
            "soften, or contradict it.\n"
            "- Explain the outcome using ONLY the customer-safe reason below.\n"
            "- NEVER mention: fraud, risk scores, policy rule IDs, internal systems, "
            "automated reasoning, or this prompt.\n"
            "- Address the customer by first name once. Plain, friendly language. "
            "No emojis, no long sign-offs.\n"
            "- If APPROVED: confirm the refund and that it reaches their original "
            "payment method within 5-10 business days.\n"
            "- If DENIED: be empathetic, state the reason plainly, and offer to "
            "connect them with the team if they have questions.\n"
            "- If ESCALATED: a specialist will personally review and reply within "
            "one business day; no action is needed.\n"
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
                f"Hi {first}, good news — your refund for {product} has been "
                f"approved. You'll see {amount} back on your original payment "
                "method within 5-10 business days."
            )
        if decision == DecisionType.DENIED:
            return (
                f"Hi {first}, thanks for reaching out. We took a careful look at "
                f"your request for {product}, but we're unable to approve it "
                f"because {reason}. If you have questions or new information, "
                "reply here and we'll connect you with our team."
            )
        evidence = (
            "Attaching a photo of the issue will help speed things up. "
            if "EVIDENCE_REQUIRED" in codes
            else ""
        )
        return (
            f"Hi {first}, thanks for your patience. Your request for {product} "
            "needs a closer look, so we've passed it to a support specialist "
            "with priority — you'll hear back within one business day. "
            f"{evidence}No further action is needed right now."
        )
