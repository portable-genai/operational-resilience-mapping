"""Local AssetInventoryPort: return the fictional technology estate (SDK-free)."""

from __future__ import annotations

from ...config import Settings
from ...domain.models import ResourceConfig
from . import _fixtures


class LocalAssetInventory:
    """Return the offline fixture estate for any scan target."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def scan(self, target: str) -> tuple[ResourceConfig, ...]:
        _ = target
        return _fixtures.RESOURCES
