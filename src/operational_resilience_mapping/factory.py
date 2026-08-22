"""Application factory: assemble the pure :class:`StudioService` from a bound container.

Kept out of ``domain/`` so the domain stays free of the container / config wiring: the domain
takes explicit ports, and this is the one place that reads them off the container.
"""

from __future__ import annotations

from .config import Container
from .domain.studio_service import StudioService


def build_studio(container: Container) -> StudioService:
    """Wire a :class:`StudioService` from the container's bound ports."""
    return StudioService(
        asset_inventory=container.asset_inventory,
        register=container.register,
        extraction=container.extraction,
        compliance=container.compliance,
        generation=container.generation,
        map_store=container.map_store,
        audit=container.audit,
        tracer=container.tracer,
        review_router=container.review_router,
    )
