"""Application factory: assemble the pure :class:`StudioService` from a bound container.

Kept out of ``domain/`` so the domain stays free of the container / config wiring: the domain
takes explicit ports, and this is the one place that reads them off the container.
"""

from __future__ import annotations

from .adapters.controls import RecordingReviewRouter
from .config import Container
from .domain.studio_service import StudioService


def build_studio(
    container: Container, *, review_router: RecordingReviewRouter | None = None
) -> StudioService:
    """Wire a :class:`StudioService` from the container's bound ports.

    A caller that reports ``review_routing`` passes a :class:`RecordingReviewRouter` around the
    bound router, so the studio's hand-offs are recorded (and a failed one absorbed and logged)
    without the domain knowing.
    """
    return StudioService(
        asset_inventory=container.asset_inventory,
        register=container.register,
        extraction=container.extraction,
        compliance=container.compliance,
        generation=container.generation,
        map_store=container.map_store,
        audit=container.audit,
        tracer=container.tracer,
        review_router=review_router or container.review_router,
    )
