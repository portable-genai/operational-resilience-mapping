"""Local GenerationPort: a DETERMINISTIC narration stub (SDK-free).

The narration is the ONLY non-deterministic part of a real deployment, so the offline adapter
replaces it with a fixed, grounded reply: it returns the narrative schema's JSON with a prose
string that carries NO figures, so with the generation adapter stubbed every engine number is
identical run to run and the groundedness metric passes trivially. It never produces a number.
"""

from __future__ import annotations

import json

from ...config import Settings
from ...domain.models import GenerationRequest, GenerationResponse

_STUB_NARRATIVE = (
    "The dependency chain, the proposed impact tolerances and the scenario outcome are set out "
    "above. Every figure is derived by the deterministic engine and cited to its regulatory "
    "basis; this narrative adds context only and introduces no new number or finding."
)


class LocalGenerationAdapter:
    """Return a fixed, schema-shaped narration for the offline ``local`` profile."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        _ = request
        return GenerationResponse(
            text=json.dumps({"narrative": _STUB_NARRATIVE}),
            model="local-stub",
        )
