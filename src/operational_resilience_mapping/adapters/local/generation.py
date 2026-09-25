"""Local GenerationPort: a DETERMINISTIC narration stub (SDK-free).

The narration is the ONLY non-deterministic part of a real deployment, so the offline adapter
replaces it with a fixed, grounded reply: it returns the narrative schema's JSON with a prose
string that carries NO figures, so with the generation adapter stubbed every engine number is
identical run to run and the groundedness metric passes trivially. It never produces a number.

It answers under :data:`~operational_resilience_mapping.config.OFFLINE_STUB_MODEL`, the name
``generator_model`` reports under ``local``, and notes that name as the model that answered, so
the console's model pill names the stub rather than a model it never called. It never notes a
search: it does not go online.
"""

from __future__ import annotations

import json

from hex_service_kit import provenance

from ...config import OFFLINE_STUB_MODEL, Settings
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
        provenance.note_model(OFFLINE_STUB_MODEL)
        return GenerationResponse(
            text=json.dumps({"narrative": _STUB_NARRATIVE}),
            model=OFFLINE_STUB_MODEL,
        )
