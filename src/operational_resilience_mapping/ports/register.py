"""RegisterReadPort: the third-party register read boundary (slice 4).

Reads Rgc8's Outsourcing and Material-Arrangements Register over A2A as DATA (Rgc9 never owns the
register; Rgc8 does). ``list_arrangements(scope)`` returns the material third-party arrangements
in scope. Rgc8 is not built in this wave, so the offline family returns a deterministic fixture
register and ``tests/contract`` freezes the contract as a fixture test; the managed family is an
A2A client that refuses when unconfigured; the on-prem family refuses.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..domain.models import ThirdPartyArrangement


@runtime_checkable
class RegisterReadPort(Protocol):
    def list_arrangements(self, scope: str) -> tuple[ThirdPartyArrangement, ...]:
        """Return the material third-party arrangements in ``scope`` from Rgc8's register."""
        ...
