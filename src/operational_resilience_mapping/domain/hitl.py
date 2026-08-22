"""Human-in-the-loop policy for the resilience studio (rule R8 / P-06).

Setting an impact tolerance is consequential and a breached scenario is consequential, so both
route to a human. ``requires_review`` is unconditionally True for a tolerance proposal;
``severity_for`` maps the chain criticality (and any scenario breach) onto the band the audit
record and the review carry. Pure decision logic; no side effects.
"""

from __future__ import annotations

from dataclasses import dataclass

from .kernel import Severity
from .models import ScenarioResult


@dataclass(frozen=True, slots=True)
class ResilienceReviewPolicy:
    """Maker-checker gate for tolerance proposals and scenario results. Pure decision logic."""

    def requires_review(self) -> bool:
        """A tolerance proposal is always human-reviewed: a maker proposes, a checker disposes."""
        return True

    def proposal_severity(self, chain_criticality: Severity) -> Severity:
        """The band a tolerance proposal carries: the chain criticality it was derived from."""
        return chain_criticality

    def scenario_severity(self, scenario: ScenarioResult) -> Severity:
        """A breached scenario is CRITICAL; a within-tolerance one carries HIGH for visibility."""
        if not scenario.within_tolerance:
            return Severity.CRITICAL
        if scenario.aggravators:
            return Severity.HIGH
        return Severity.MEDIUM
