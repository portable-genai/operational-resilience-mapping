"""Module-specific types for the concentration-and-exit engine.

Reuses the shared kernel (``Citation``, ``Severity``, ``SEVERITY_RANK``, ``utcnow``) and defines
only the concentration/portability types here. No dependency on Google Cloud, ADK or FastAPI:
pure standard library, exactly like the rest of ``domain/``.
"""

from __future__ import annotations

from dataclasses import dataclass

from hex_service_kit.enums import LenientStrEnum

from ..kernel import Citation, Severity


class RiskLevel(LenientStrEnum):
    """Risk level for a concentration / lock-in finding (mirrors Severity ranking)."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


#: Rank for comparing risk levels (higher == worse).
RISK_RANK: dict[RiskLevel, int] = {
    RiskLevel.LOW: 0,
    RiskLevel.MEDIUM: 1,
    RiskLevel.HIGH: 2,
    RiskLevel.CRITICAL: 3,
}


class ServiceCategory(LenientStrEnum):
    """The category of a cloud service, which drives the default portability rating."""

    COMPUTE = "compute"
    STORAGE = "storage"
    DB = "db"
    ML = "ml"
    NETWORK = "network"
    ANALYTICS = "analytics"
    OTHER = "other"


class PortabilityRating(LenientStrEnum):
    """How portable a service is off the current provider (the lock-in axis)."""

    PORTABLE = "PORTABLE"
    PARTIAL = "PARTIAL"
    LOCKED = "LOCKED"


class Effort(LenientStrEnum):
    """Estimated migration effort to reach the portable target."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ConcentrationDimension(LenientStrEnum):
    """The dimension along which concentration / lock-in is assessed."""

    SINGLE_PROVIDER = "single_provider"
    SINGLE_REGION = "single_region"
    CRITICAL_SERVICE = "critical_service"
    DATA_GRAVITY = "data_gravity"


@dataclass(frozen=True, slots=True)
class CloudService:
    """One cloud service the bank has deployed (a third-party / technology dependency).

    ``managed`` is True for a proprietary managed service (the lock-in surface) and False for a
    portable building block. ``criticality`` is the business criticality; a critical service
    concentrated on one provider / region is what drives a concentration finding.
    """

    id: str
    name: str
    category: ServiceCategory
    criticality: Severity = Severity.MEDIUM
    region: str | None = None
    provider: str = "gcp"
    managed: bool = True
    tenant: str = ""


@dataclass(frozen=True, slots=True)
class ServicePortability:
    """Per cloud-service exit assessment.

    The deterministic :class:`PortabilityPolicy` sets ``rating`` / ``portable_target`` /
    ``open_standard`` from the service category; a model may enrich ``migration_steps`` with prose
    but never lowers a LOCKED rating.
    """

    service: CloudService
    rating: PortabilityRating
    portable_target: str
    open_standard: str
    migration_steps: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    effort: Effort = Effort.MEDIUM
    citations: tuple[Citation, ...] = ()

    @property
    def service_id(self) -> str:
        return self.service.id

    @property
    def is_locked(self) -> bool:
        return self.rating is PortabilityRating.LOCKED


@dataclass(frozen=True, slots=True)
class ConcentrationFinding:
    """A concentration / provider-lock-in finding.

    Each finding names the ``dimension``, a ``level`` (risk), a human ``detail``, the
    ``regulatory_ref`` it maps to (APRA CPS 230 / MAS / HKMA outsourcing), and a ``remediation``.
    ``citations`` are populated from the grounded compliance answer; the deterministic detector
    leaves them empty so a replay of the detector alone is byte-identical.
    """

    dimension: ConcentrationDimension
    level: RiskLevel
    detail: str
    regulatory_ref: str
    remediation: str
    citations: tuple[Citation, ...] = ()
