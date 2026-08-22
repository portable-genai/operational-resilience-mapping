"""On-prem AssetInventoryPort: fail-fast portability placeholder (P-12)."""

from __future__ import annotations

from ...config import Settings
from ...domain.models import ResourceConfig


class OnPremAssetInventory:
    """Satisfies AssetInventoryPort but refuses: the client wires its own CMDB / inventory."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def scan(self, target: str) -> tuple[ResourceConfig, ...]:
        raise NotImplementedError(
            "on-prem asset inventory is a portability placeholder: bind the client's own CMDB"
        )
