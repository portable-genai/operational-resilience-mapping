"""RegisterReadPort: the third-party register read boundary (slice 4).

Reads third-party-risk-ddq's Outsourcing and Material-Arrangements Register over A2A as DATA
(operational-resilience-mapping never owns the register; third-party-risk-ddq does).
``list_arrangements(scope)`` returns the material third-party arrangements in scope.
third-party-risk-ddq is not built in this wave, so the offline family returns a deterministic
fixture register and ``tests/contract`` freezes the contract as a fixture test; the managed family
is an A2A client that refuses when unconfigured; the on-prem family refuses.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..domain.models import ThirdPartyArrangement


@runtime_checkable
class RegisterReadPort(Protocol):
    def list_arrangements(self, scope: str) -> tuple[ThirdPartyArrangement, ...]:
        """Return the material third-party arrangements in ``scope`` from third-party-risk-ddq's
        register.
        """
        ...
