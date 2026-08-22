"""Local RegisterReadPort: return the fictional outsourcing register (SDK-free).

Rgc8 is unbuilt in this wave, so this fixture register is the frozen contract Rgc9 reads over
A2A. The contract fixture test asserts the shape so the live Rgc8 feed swaps in unchanged.
"""

from __future__ import annotations

from ...config import Settings
from ...domain.models import ThirdPartyArrangement
from . import _fixtures


class LocalRegisterAdapter:
    """Return the offline fixture third-party arrangements for any scope."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def list_arrangements(self, scope: str) -> tuple[ThirdPartyArrangement, ...]:
        _ = scope
        return _fixtures.ARRANGEMENTS
