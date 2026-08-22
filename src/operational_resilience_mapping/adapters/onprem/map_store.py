"""On-prem MapStorePort: fail-fast portability placeholder (P-12)."""

from __future__ import annotations

from ...config import Settings
from ...domain.models import ResilienceMap

_MSG = "on-prem map store is a portability placeholder: bind the client's own database"


class OnPremMapStore:
    """Satisfies MapStorePort but refuses: the client wires its own store."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def save_map(self, resilience_map: ResilienceMap, *, tenant: str = "") -> str:
        raise NotImplementedError(_MSG)

    def get_map(self, service_id: str, *, tenant: str = "") -> ResilienceMap | None:
        raise NotImplementedError(_MSG)
