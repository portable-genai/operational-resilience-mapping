"""Deterministic per-service portability baseline.

Given a :class:`CloudService` it returns a deterministic baseline portability rating, the
open-standard portable target, and a default migration effort, derived from the service category
and whether the service is a proprietary managed service. A model may enrich the migration steps
with prose, but it never sets a rating and never lowers a LOCKED rating silently.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import CloudService, Effort, PortabilityRating, ServiceCategory


@dataclass(frozen=True, slots=True)
class PortabilityBaseline:
    """The deterministic baseline for one service category (before any prose enrichment)."""

    rating: PortabilityRating
    portable_target: str
    open_standard: str
    effort: Effort


_BASELINE_BY_CATEGORY: dict[ServiceCategory, PortabilityBaseline] = {
    ServiceCategory.COMPUTE: PortabilityBaseline(
        rating=PortabilityRating.PORTABLE,
        portable_target="GKE / OCI containers on Google Distributed Cloud or any operator",
        open_standard="OCI image + Kubernetes",
        effort=Effort.LOW,
    ),
    ServiceCategory.STORAGE: PortabilityBaseline(
        rating=PortabilityRating.PARTIAL,
        portable_target="S3-compatible / POSIX object store on Google Distributed Cloud",
        open_standard="S3 API / open object formats (Parquet, Avro)",
        effort=Effort.MEDIUM,
    ),
    ServiceCategory.DB: PortabilityBaseline(
        rating=PortabilityRating.PARTIAL,
        portable_target="open PostgreSQL on Google Distributed Cloud or self-managed",
        open_standard="ANSI SQL / pg_dump / logical replication",
        effort=Effort.MEDIUM,
    ),
    ServiceCategory.ML: PortabilityBaseline(
        rating=PortabilityRating.LOCKED,
        portable_target="containerised open-weight model served on Kubernetes",
        open_standard="ONNX / open model weights + KServe",
        effort=Effort.HIGH,
    ),
    ServiceCategory.NETWORK: PortabilityBaseline(
        rating=PortabilityRating.PARTIAL,
        portable_target="open load balancer / DNS (ingress controller, external DNS)",
        open_standard="Kubernetes Ingress / standard DNS",
        effort=Effort.MEDIUM,
    ),
    ServiceCategory.ANALYTICS: PortabilityBaseline(
        rating=PortabilityRating.PARTIAL,
        portable_target="open lakehouse on Google Distributed Cloud (open table formats)",
        open_standard="Parquet / Iceberg + open query engine",
        effort=Effort.HIGH,
    ),
    ServiceCategory.OTHER: PortabilityBaseline(
        rating=PortabilityRating.PARTIAL,
        portable_target="re-platform to an open-standard equivalent",
        open_standard="open API / open data format",
        effort=Effort.MEDIUM,
    ),
}

_PORTABLE_BASELINE = PortabilityBaseline(
    rating=PortabilityRating.PORTABLE,
    portable_target="lift-and-shift to any operator (already open-standard)",
    open_standard="open standard already in use",
    effort=Effort.LOW,
)


class PortabilityPolicy:
    """Deterministic per-service portability rating + portable target (pure, testable)."""

    def __init__(
        self,
        baselines: dict[ServiceCategory, PortabilityBaseline] | None = None,
    ) -> None:
        self._baselines = dict(baselines or _BASELINE_BY_CATEGORY)

    def baseline_for(self, service: CloudService) -> PortabilityBaseline:
        """Return the deterministic portability baseline for ``service``."""
        if not service.managed:
            return _PORTABLE_BASELINE
        return self._baselines.get(service.category, _BASELINE_BY_CATEGORY[ServiceCategory.OTHER])

    def rating_for(self, service: CloudService) -> PortabilityRating:
        """The deterministic portability rating for ``service`` (the lock-in axis)."""
        return self.baseline_for(service).rating

    def assess(self, service: CloudService) -> ServicePortabilityResult:
        """Return the full baseline assessment for ``service`` (rating + target + effort)."""
        return self.baseline_for(service)


#: Type alias kept for readability at call sites.
ServicePortabilityResult = PortabilityBaseline
