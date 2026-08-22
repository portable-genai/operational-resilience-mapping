"""GCP GenerationPort: Gemini narration (SDK imports stay lazy)."""

from __future__ import annotations

from ...config import Settings
from ...domain.models import GenerationRequest, GenerationResponse


class CloudGenerationAdapter:
    """Draft narratives with Gemini. The SDK import lives inside the method so the offline
    profiles import this module with no cloud SDK installed. The model narrates only.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def generate(
        self, request: GenerationRequest
    ) -> GenerationResponse:  # pragma: no cover - needs live GCP
        from google import genai

        _ = (genai, request)
        raise NotImplementedError("Gemini narration is wired at deploy time")
