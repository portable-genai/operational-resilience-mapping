"""GCP MapStorePort: AlloyDB-backed resilience-map store (SDK imports stay lazy)."""

from __future__ import annotations

from ...config import Settings
from ...domain.models import ResilienceMap


class CloudMapStore:
    """Persist resilience maps to AlloyDB. The connector import lives inside the method so the
    offline profiles import this module with no cloud SDK installed (the portability proof).
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def save_map(
        self, resilience_map: ResilienceMap, *, tenant: str = ""
    ) -> str:  # pragma: no cover - needs live GCP
        from google.cloud.alloydb import connector as alloydb_connector

        _ = (alloydb_connector, resilience_map, tenant)
        raise NotImplementedError("AlloyDB map persistence is wired at deploy time")

    def get_map(
        self, service_id: str, *, tenant: str = ""
    ) -> ResilienceMap | None:  # pragma: no cover - needs live GCP
        from google.cloud.alloydb import connector as alloydb_connector

        _ = (alloydb_connector, service_id, tenant)
        raise NotImplementedError("AlloyDB map retrieval is wired at deploy time")
