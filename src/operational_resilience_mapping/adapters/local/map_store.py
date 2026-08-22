"""Local MapStorePort: an in-memory, tenant-partitioned resilience-map store (SDK-free).

Answers offline: a saved map round-trips byte-identical, which is what the contract replay test
asserts. Tenant isolation is honoured here too (a map is keyed by tenant + service id), but the
authoritative 403-not-404 check lives in the studio service against the verified principal.
"""

from __future__ import annotations

from ...config import Settings
from ...domain.models import ResilienceMap


class LocalMapStore:
    """Store resilience maps in a per-instance dict for the offline ``local`` profile."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._maps: dict[tuple[str, str], ResilienceMap] = {}

    def save_map(self, resilience_map: ResilienceMap, *, tenant: str = "") -> str:
        key = (tenant, resilience_map.service.id)
        self._maps[key] = resilience_map
        return f"map:{tenant}:{resilience_map.service.id}"

    def get_map(self, service_id: str, *, tenant: str = "") -> ResilienceMap | None:
        return self._maps.get((tenant, service_id))
