"""Refund Policy Validator tool — the deterministic heart of adjudication.

Encodes every rule in ``data/refund_policy.md`` as an explicit check, returning a
structured :class:`PolicyResult` of violations tagged ``HARD`` / ``SOFT``. The
decision service (not this tool, and never the LLM) composes the final outcome
from these violations plus the fraud result.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from langchain_core.tools import StructuredTool

from app.config import get_settings
from app.schemas.customer import CustomerProfile, OrderInfo
from app.schemas.decision import FraudResult, PolicyResult, PolicyViolation

_SIX_MONTHS_DAYS = 182
_DAMAGE_KEYWORDS = ("damag", "defect", "broken", "cracked", "faulty")


def _parse_date(value: str) -> date:
    """Parse an ISO-8601 ``YYYY-MM-DD`` string into a :class:`date`."""
    return datetime.strptime(value, "%Y-%m-%d").date()


class PolicyValidatorTool:
    """Validate a refund request against the refund policy rules R1–R7."""

    name = "policy_validator"
    description = (
        "Validate a refund against policy: window, product eligibility, "
        "refund frequency, fraud, evidence, and data completeness."
    )

    def __init__(
        self,
        reference_date: date | None = None,
        window_days: int | None = None,
        max_refunds: int | None = None,
    ) -> None:
        """Inject policy knobs and a reference 'today' (for testability)."""
        settings = get_settings()
        self._today = reference_date or date.today()
        self._window_days = window_days or settings.refund_window_days
        self._max_refunds = max_refunds or settings.max_refunds_per_6_months

    def run(
        self,
        customer: CustomerProfile,
        order: OrderInfo,
        reason: str,
        fraud: FraudResult | None = None,
        evidence_provided: bool = False,
    ) -> PolicyResult:
        """Evaluate policy rules R1–R7 and return the structured result.

        ``fraud`` is optional: in the graph it is ``None`` because fraud runs in
        a dedicated downstream node and is composed by the decision service.
        When provided (e.g. in unit tests of the tool in isolation), the fraud
        rule R5 is evaluated here too.

        Args:
            customer: The resolved customer profile.
            order: The resolved order.
            reason: The customer's stated refund reason.
            fraud: The fraud assessment, or ``None`` to skip rule R5 here.
            evidence_provided: Whether photographic evidence was attached.

        Returns:
            A :class:`PolicyResult` whose ``approved`` flag is ``True`` only when
            there are no ``HARD`` violations.
        """
        violations: list[PolicyViolation] = []
        violations += self._check_window(customer, order)
        violations += self._check_product_eligibility(order)
        violations += self._check_refund_frequency(customer)
        if fraud is not None:
            violations += self._check_fraud(fraud)
        violations += self._check_evidence(reason, evidence_provided)
        violations += self._check_data_completeness(customer, order, reason)

        approved = not any(v.severity == "HARD" for v in violations)
        return PolicyResult(approved=approved, violations=violations)

    # ── Individual rule checks (each ≤ a handful of lines) ──────────────────
    def _check_window(
        self, customer: CustomerProfile, order: OrderInfo
    ) -> list[PolicyViolation]:
        """R1 — refund window; downgraded to SOFT for VIP customers."""
        age = (self._today - _parse_date(order.purchase_date)).days
        if age <= self._window_days:
            return []
        severity = "SOFT" if customer.tier == "vip" else "HARD"
        return [
            PolicyViolation(
                rule_id="R1",
                reason_code="WINDOW_EXCEEDED",
                severity=severity,
                message=(
                    f"Purchased {age} days ago, exceeding the {self._window_days}-day "
                    f"window{' (VIP — eligible for review)' if severity == 'SOFT' else ''}."
                ),
            )
        ]

    def _check_product_eligibility(self, order: OrderInfo) -> list[PolicyViolation]:
        """R2/R3 — final-sale and digital products are non-refundable."""
        out: list[PolicyViolation] = []
        if order.is_final_sale:
            out.append(
                PolicyViolation(
                    rule_id="R2",
                    reason_code="FINAL_SALE",
                    severity="HARD",
                    message="Final-sale items are non-refundable.",
                )
            )
        if order.is_digital:
            out.append(
                PolicyViolation(
                    rule_id="R3",
                    reason_code="DIGITAL_NON_REFUNDABLE",
                    severity="HARD",
                    message="Digital products are non-refundable once delivered.",
                )
            )
        return out

    def _check_refund_frequency(
        self, customer: CustomerProfile
    ) -> list[PolicyViolation]:
        """R4 — at most 3 approved refunds in a rolling 6-month window."""
        cutoff = self._today - timedelta(days=_SIX_MONTHS_DAYS)
        recent = [
            r
            for r in customer.refund_history
            if r.status == "approved" and _parse_date(r.date) >= cutoff
        ]
        if len(recent) < self._max_refunds:
            return []
        return [
            PolicyViolation(
                rule_id="R4",
                reason_code="REFUND_LIMIT_EXCEEDED",
                severity="HARD",
                message=(
                    f"{len(recent)} approved refunds in the last 6 months "
                    f"(limit {self._max_refunds})."
                ),
            )
        ]

    def _check_fraud(self, fraud: FraudResult) -> list[PolicyViolation]:
        """R5 — fraud threshold (HARD) and borderline band (SOFT)."""
        if fraud.band == "high":
            return [
                PolicyViolation(
                    rule_id="R5",
                    reason_code="FRAUD_THRESHOLD",
                    severity="HARD",
                    message=f"Fraud score {fraud.risk_score} ≥ threshold {fraud.threshold}.",
                )
            ]
        if fraud.band == "borderline":
            return [
                PolicyViolation(
                    rule_id="R5",
                    reason_code="FRAUD_BORDERLINE",
                    severity="SOFT",
                    message=f"Fraud score {fraud.risk_score} is borderline; needs review.",
                )
            ]
        return []

    def _check_evidence(
        self, reason: str, evidence_provided: bool
    ) -> list[PolicyViolation]:
        """R6 — damage/defect claims require evidence (SOFT → escalate)."""
        is_damage_claim = any(k in reason.lower() for k in _DAMAGE_KEYWORDS)
        if is_damage_claim and not evidence_provided:
            return [
                PolicyViolation(
                    rule_id="R6",
                    reason_code="EVIDENCE_REQUIRED",
                    severity="SOFT",
                    message="Damage/defect claim without photographic evidence.",
                )
            ]
        return []

    def _check_data_completeness(
        self, customer: CustomerProfile, order: OrderInfo, reason: str
    ) -> list[PolicyViolation]:
        """R7 — order must belong to the customer and a reason must be present."""
        out: list[PolicyViolation] = []
        if order.customer_id != customer.customer_id:
            out.append(
                PolicyViolation(
                    rule_id="R7",
                    reason_code="INSUFFICIENT_DATA",
                    severity="SOFT",
                    message="Order does not belong to this customer.",
                )
            )
        if not reason or not reason.strip():
            out.append(
                PolicyViolation(
                    rule_id="R7",
                    reason_code="INSUFFICIENT_DATA",
                    severity="SOFT",
                    message="No refund reason provided.",
                )
            )
        return out

    def as_tool(self) -> StructuredTool:
        """Adapt :meth:`run` into a LangChain ``StructuredTool``."""

        def _invoke(
            customer: dict, order: dict, reason: str, fraud: dict, evidence_provided: bool = False
        ) -> dict:
            return self.run(
                CustomerProfile.model_validate(customer),
                OrderInfo.model_validate(order),
                reason,
                FraudResult.model_validate(fraud),
                evidence_provided,
            ).model_dump()

        return StructuredTool.from_function(
            func=_invoke, name=self.name, description=self.description
        )
