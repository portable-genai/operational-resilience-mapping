"""AssetInventoryPort: the technology-dependency discovery boundary (slice 4).

Cribbed from architecture-validator's ``IaCScannerPort``: ``scan(target)`` over a project / folder /
org scope returns normalised resource configs (the technology chain). The offline family returns a
fictional estate, the managed family reads Cloud Asset Inventory with lazy imports, the on-prem
family refuses.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..domain.models import ResourceConfig


@runtime_checkable
class AssetInventoryPort(Protocol):
    def scan(self, target: str) -> tuple[ResourceConfig, ...]:
        """Return the normalised technology resources in ``target`` (the tech dependency chain)."""
        ...
