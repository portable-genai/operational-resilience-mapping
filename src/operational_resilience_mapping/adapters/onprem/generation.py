"""On-prem GenerationPort: fail-fast portability placeholder (P-12)."""

from __future__ import annotations

from ...config import Settings
from ...domain.models import GenerationRequest, GenerationResponse


class OnPremGenerationAdapter:
    """Satisfies GenerationPort but refuses: the client wires its own model endpoint."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        raise NotImplementedError(
            "on-prem narration is a portability placeholder: bind the client's own model endpoint"
        )
