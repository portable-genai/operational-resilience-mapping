"""Maker-checker policy for the concentration-and-exit module.

An exit / concentration assessment is consequential, so ``requires_review`` is unconditionally
True. ``escalates`` is True when a critical service is LOCKED or a concentration finding is at or
above HIGH. Pure decision logic; no side effects.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..kernel import SEVERITY_RANK, Severity
from .models import (
    RISK_RANK,
    ConcentrationFinding,
    RiskLevel,
    ServicePortability,
)

_ESCALATION_FLOOR: RiskLevel = RiskLevel.HIGH


@dataclass(frozen=True, slots=True)
class ExitReviewPolicy:
    """Maker-checker gate for concentration-and-exit assessments. Pure decision logic."""

    escalation_floor: RiskLevel = _ESCALATION_FLOOR

    def requires_review(
        self,
        services: list[ServicePortability],
        concentration: list[ConcentrationFinding],
    ) -> bool:
        """Whether the assessment needs human review. Always True: it is consequential."""
        _ = (services, concentration)
        return True

    def escalates(
        self,
        services: list[ServicePortability],
        concentration: list[ConcentrationFinding],
    ) -> bool:
        """Whether it escalates to senior review (LOCKED critical or HIGH concentration)."""
        if self._has_locked_critical(services):
            return True
        floor = RISK_RANK[self.escalation_floor]
        return any(RISK_RANK[f.level] >= floor for f in concentration)

    @staticmethod
    def _has_locked_critical(services: list[ServicePortability]) -> bool:
        crit_floor = SEVERITY_RANK[Severity.HIGH]
        return any(
            s.is_locked and SEVERITY_RANK[s.service.criticality] >= crit_floor for s in services
        )
