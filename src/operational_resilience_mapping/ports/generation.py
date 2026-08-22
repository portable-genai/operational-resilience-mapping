"""GenerationPort: the model-narration boundary (slices 4, 5 and 7).

The model narrates only: it drafts service narratives, gap explanations and tolerance
justifications, always schema-validated and discarded on failure. It never produces a
consequential number. The offline family returns a DETERMINISTIC stub reply, so with the
generation adapter stubbed every engine number is identical run to run; the managed family calls
Gemini with lazy imports; the on-prem family refuses.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..domain.models import GenerationRequest, GenerationResponse


@runtime_checkable
class GenerationPort(Protocol):
    def generate(self, request: GenerationRequest) -> GenerationResponse:
        """Return the model's narration for ``request`` (schema-validated by the caller)."""
        ...
