"""On-prem CompliancePort: fail-fast portability placeholder (P-12)."""

from __future__ import annotations

from ...config import Settings
from ...domain.models import ComplianceAnswer


class OnPremComplianceAdapter:
    """Satisfies CompliancePort but refuses: the client wires its own compliance KB."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def requirements(self, question: str, actor: str) -> ComplianceAnswer:
        raise NotImplementedError(
            "on-prem compliance read is a portability placeholder: bind the client's own KB"
        )
