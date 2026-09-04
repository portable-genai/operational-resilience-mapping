"""CompliancePort: the regulatory-grounding boundary (slices 5 and the concentration module).

Asks compliance-advisory's compliance knowledge base for the operational-resilience / outsourcing
rule text that grounds a tolerance basis or a concentration finding, and returns it with citations.
The studio never invents regulatory text; a finding cites the answer compliance-advisory returned.
The offline family returns a fixture answer, the managed family is an A2A client that refuses when
unconfigured, the on-prem family refuses.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..domain.models import ComplianceAnswer


@runtime_checkable
class CompliancePort(Protocol):
    def requirements(self, question: str, actor: str) -> ComplianceAnswer:
        """Return the grounded regulatory requirement (text + citations) for ``question``."""
        ...
