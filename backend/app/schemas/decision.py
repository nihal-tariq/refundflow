"""Schemas for policy validation, fraud results, and the final decision."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class DecisionType(StrEnum):
    """The three terminal outcomes of the refund workflow."""

    APPROVED = "APPROVED"
    DENIED = "DENIED"
    ESCALATED = "ESCALATED"


class PolicyViolation(BaseModel):
    """A single policy rule violation with its severity and human reason."""

    rule_id: str = Field(description="Policy rule id, e.g. 'R1'.")
    reason_code: str = Field(description="Machine code, e.g. 'WINDOW_EXCEEDED'.")
    severity: str = Field(description="HARD | SOFT")
    message: str


class PolicyResult(BaseModel):
    """Output of the policy validator tool.

    ``approved`` is ``True`` only when no ``HARD`` violations are present. The
    decision node still inspects ``SOFT`` violations to decide escalation.
    """

    approved: bool
    violations: list[PolicyViolation] = Field(default_factory=list)

    @property
    def hard_violations(self) -> list[PolicyViolation]:
        """Return only the HARD (auto-deny) violations."""
        return [v for v in self.violations if v.severity == "HARD"]

    @property
    def soft_violations(self) -> list[PolicyViolation]:
        """Return only the SOFT (escalation-candidate) violations."""
        return [v for v in self.violations if v.severity == "SOFT"]


class FraudResult(BaseModel):
    """Output of the fraud-check tool."""

    risk_score: float = Field(ge=0.0, le=1.0)
    band: str = Field(description="low | borderline | high")
    threshold: float
