"""GCP AssetInventoryPort: Cloud Asset Inventory (SDK imports stay lazy)."""

from __future__ import annotations

from ...config import Settings
from ...domain.models import ResourceConfig


class CloudAssetInventory:
    """Read technology dependencies from Cloud Asset Inventory. The SDK import lives inside the
    method so the offline profiles import this module with no cloud SDK installed.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def scan(self, target: str) -> tuple[ResourceConfig, ...]:  # pragma: no cover - needs live GCP
        from google.cloud import asset_v1

        _ = (asset_v1, target)
        raise NotImplementedError("Cloud Asset Inventory scan is wired at deploy time")
