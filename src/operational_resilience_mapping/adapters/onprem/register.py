"""On-prem RegisterReadPort: fail-fast portability placeholder (P-12)."""

from __future__ import annotations

from ...config import Settings
from ...domain.models import ThirdPartyArrangement


class OnPremRegisterAdapter:
    """Satisfies RegisterReadPort but refuses: the client wires its own register feed."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def list_arrangements(self, scope: str) -> tuple[ThirdPartyArrangement, ...]:
        raise NotImplementedError(
            "on-prem register read is a portability placeholder: bind the client's own register"
        )
