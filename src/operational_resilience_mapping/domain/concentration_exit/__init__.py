"""The concentration-and-exit module: cloud concentration and sovereign-exit analysis.

A namespaced subpackage rather than a separate system, on the same pattern as
``architecture_validator``'s ``domain/residency/``: it reuses operational-resilience-mapping's
shared kernel types (``Citation``, ``Severity``, ``utcnow``, ``SEVERITY_RANK``) and keeps only the
module-specific types (``CloudService``, ``ServicePortability``, ``ConcentrationFinding``,
``RiskLevel``) local.

The four deterministic concentration dimensions (SINGLE_PROVIDER, SINGLE_REGION,
CRITICAL_SERVICE, DATA_GRAVITY) and the per-service portability baseline are pure stdlib, and
``tests/unit/test_concentration_exit_parity.py`` replays the golden set and asserts the
findings are unchanged. In operational-resilience-mapping the concentration
findings register as scenario aggravators (a LOCKED critical service failing its exit path),
which is what the scenario engine consumes.
"""

from __future__ import annotations

from .concentration_service import ConcentrationService
from .hitl import ExitReviewPolicy
from .models import (
    RISK_RANK,
    CloudService,
    ConcentrationDimension,
    ConcentrationFinding,
    Effort,
    PortabilityRating,
    RiskLevel,
    ServiceCategory,
    ServicePortability,
)
from .portability_policy import PortabilityBaseline, PortabilityPolicy

__all__ = [
    "RISK_RANK",
    "CloudService",
    "ConcentrationDimension",
    "ConcentrationFinding",
    "ConcentrationService",
    "Effort",
    "ExitReviewPolicy",
    "PortabilityBaseline",
    "PortabilityPolicy",
    "PortabilityRating",
    "RiskLevel",
    "ServiceCategory",
    "ServicePortability",
]
