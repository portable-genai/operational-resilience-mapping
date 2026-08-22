"""Local CompliancePort: return the grounded fixture regulatory answer (SDK-free).

Rsk1 is read as data; this fixture answer is the frozen contract. The studio grounds every
tolerance basis and concentration finding on the citations this returns, so it never invents
regulatory text.
"""

from __future__ import annotations

from ...config import Settings
from ...domain.models import ComplianceAnswer
from . import _fixtures


class LocalComplianceAdapter:
    """Return the offline fixture compliance answer for any question."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def requirements(self, question: str, actor: str) -> ComplianceAnswer:
        _ = (question, actor)
        return _fixtures.COMPLIANCE_ANSWER
