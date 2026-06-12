"""Decision service — composes the final APPROVE/DENY/ESCALATE outcome.

This is the single place where the terminal decision is *made*. It consumes the
deterministic policy and fraud results and applies the decision matrix from
``refund_policy.md``. Keeping it out of the LangGraph node (which only
orchestrates) honours "no business logic in nodes" and makes the decision a pure
function that is exhaustively unit-testable.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas.customer import CustomerProfile
from app.schemas.decision import (
    DecisionType,
    FraudResult,
    PolicyResult,
    PolicyViolation,
)


@dataclass(frozen=True)
class DecisionOutcome:
    """Result of decision composition: the verdict plus a human rationale."""

    decision: DecisionType
    rationale: str
    reason_codes: list[str]


def _fraud_violation(fraud: FraudResult) -> PolicyViolation | None:
    """Map a fraud band to its policy violation (R5), or ``None`` if low risk.

    The fraud node runs separately from policy validation, so the fraud→policy
    mapping lives here where policy and fraud signals are composed.
    """
    if fraud.band == "high":
        return PolicyViolation(
            rule_id="R5",
            reason_code="FRAUD_THRESHOLD",
            severity="HARD",
            message=f"Fraud score {fraud.risk_score} ≥ threshold {fraud.threshold}.",
        )
    if fraud.band == "borderline":
        return PolicyViolation(
            rule_id="R5",
            reason_code="FRAUD_BORDERLINE",
            severity="SOFT",
            message=f"Fraud score {fraud.risk_score} is borderline; needs review.",
        )
    return None


class DecisionService:
    """Compose a terminal refund decision from policy + fraud signals."""

    def decide(
        self,
        customer: CustomerProfile,
        policy: PolicyResult,
        fraud: FraudResult,
    ) -> DecisionOutcome:
        """Return the terminal decision for a refund request.

        Decision matrix (see ``refund_policy.md``):

        * Any ``HARD`` violation                       → **DENIED**
        * Only ``SOFT`` signals present                → **ESCALATED**
        * No violations and fraud below borderline     → **APPROVED**

        Args:
            customer: The customer profile (used to explain conflicting signals).
            policy: The structured policy validation result.
            fraud: The fraud assessment.

        Returns:
            A :class:`DecisionOutcome`.
        """
        # Compose policy violations with the separately-computed fraud signal.
        all_violations = list(policy.violations)
        fraud_v = _fraud_violation(fraud)
        if fraud_v is not None:
            all_violations.append(fraud_v)
        hard = [v for v in all_violations if v.severity == "HARD"]
        soft = [v for v in all_violations if v.severity == "SOFT"]

        if hard:
            codes = [v.reason_code for v in hard]
            rationale = "Refund denied due to policy violation(s): " + "; ".join(
                v.message for v in hard
            )
            return DecisionOutcome(DecisionType.DENIED, rationale, codes)

        if soft:
            codes = [v.reason_code for v in soft]
            rationale = self._escalation_rationale(customer, soft, fraud)
            return DecisionOutcome(DecisionType.ESCALATED, rationale, codes)

        rationale = (
            f"All policy checks passed and fraud risk is low "
            f"({fraud.risk_score} < {fraud.threshold}). Refund approved."
        )
        return DecisionOutcome(DecisionType.APPROVED, rationale, [])

    def _escalation_rationale(
        self,
        customer: CustomerProfile,
        soft: list,
        fraud: FraudResult,
    ) -> str:
        """Explain *why* signals conflict, for the human reviewer."""
        positives: list[str] = []
        if customer.tier == "vip":
            positives.append("VIP standing")
        if customer.lifetime_value >= 2000:
            positives.append(f"high lifetime value (${customer.lifetime_value:,.0f})")
        if not customer.refund_history:
            positives.append("clean refund history")
        if customer.account_age_days < 30:
            positives.append("very new account (limited history)")

        positive_text = ", ".join(positives) if positives else "no offsetting signals"
        soft_text = "; ".join(v.message for v in soft)
        return (
            "Escalated to human review: conflicting signals. "
            f"Soft concerns — {soft_text}. Customer context — {positive_text}. "
            "A human must weigh these before a final decision."
        )
