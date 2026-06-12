"""Fraud Check tool — derives a risk score and risk band for a customer.

In a real system this would call a fraud-scoring microservice. Here it derives a
deterministic score from the CRM profile, lightly adjusted by signals (denied
refund history, very new accounts) so the demo is explainable and reproducible.
"""

from __future__ import annotations

from langchain_core.tools import StructuredTool

from app.config import get_settings
from app.schemas.customer import CustomerProfile
from app.schemas.decision import FraudResult


class FraudCheckTool:
    """Compute a fraud :class:`FraudResult` for a customer profile."""

    name = "fraud_check"
    description = "Compute a fraud risk score (0-1) and band for a customer."

    def __init__(self, threshold: float | None = None, band: float | None = None) -> None:
        """Inject thresholds (default to configured policy knobs)."""
        settings = get_settings()
        self._threshold = threshold if threshold is not None else settings.fraud_score_threshold
        self._band = band if band is not None else settings.fraud_escalation_band

    def run(self, customer: CustomerProfile) -> FraudResult:
        """Return the fraud assessment for ``customer``.

        The base score is the CRM ``fraud_risk_score`` nudged upward by recent
        denied refunds and brand-new accounts, then clamped to ``[0, 1]``.

        Args:
            customer: The customer profile under assessment.

        Returns:
            A :class:`FraudResult` with score, band, and the active threshold.
        """
        score = customer.fraud_risk_score
        denied = sum(1 for r in customer.refund_history if r.status == "denied")
        score += 0.03 * denied
        if customer.account_age_days < 30:
            score += 0.05
        score = max(0.0, min(1.0, round(score, 4)))

        if score >= self._threshold:
            band = "high"
        elif score >= self._threshold - self._band:
            band = "borderline"
        else:
            band = "low"

        return FraudResult(risk_score=score, band=band, threshold=self._threshold)

    def as_tool(self) -> StructuredTool:
        """Adapt :meth:`run` into a LangChain ``StructuredTool``."""
        return StructuredTool.from_function(
            func=lambda customer: self.run(
                CustomerProfile.model_validate(customer)
            ).model_dump(),
            name=self.name,
            description=self.description,
        )
