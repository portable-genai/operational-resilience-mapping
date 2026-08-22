"""MapStorePort: the resilience-map persistence boundary (slice 3).

Stores and retrieves a :class:`ResilienceMap` for one important business service. Tenant
isolation is enforced in the domain, not here: a caller may only read a map tagged with its own
verified tenant, and a mismatch is a 403 (authorise against the verified principal, never a 404
that leaks existence). The port itself is a plain key-value contract; the offline family answers
from an in-memory store, the managed family from AlloyDB, the on-prem family refuses.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..domain.models import ResilienceMap


@runtime_checkable
class MapStorePort(Protocol):
    def save_map(self, resilience_map: ResilienceMap, *, tenant: str = "") -> str:
        """Persist ``resilience_map`` for its service and return the storage key."""
        ...

    def get_map(self, service_id: str, *, tenant: str = "") -> ResilienceMap | None:
        """Return the stored map for ``service_id``, or ``None`` when there is none."""
        ...
