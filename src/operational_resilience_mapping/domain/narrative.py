"""Grounded narration: schema-validated model output, discarded on failure (slices 5 and 7).

The model narrates only. Its reply is parsed and validated against a tiny JSON schema; anything
that does not validate is discarded and the deterministic prose stands in, so a malformed or
hallucinated reply can never change a number or add a finding. Every figure the narrative quotes
must already be in the engine output; :func:`numbers_are_grounded` is the offline check the eval
uses to reject a narrative that invents a figure.
"""

from __future__ import annotations

import json
import re
from typing import Any

from .models import GenerationRequest, GenerationResponse

#: The narration schema: the model returns a single ``narrative`` string and nothing consequential.
NARRATIVE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"narrative": {"type": "string"}},
    "required": ["narrative"],
}

_NUMBER = re.compile(r"\d[\d,]*")


def build_request(system_instruction: str, prompt: str) -> GenerationRequest:
    """Build a narration request that pins the response to the narrative schema."""
    return GenerationRequest(
        system_instruction=system_instruction,
        prompt=prompt,
        response_schema=NARRATIVE_SCHEMA,
    )


def parse_narrative(response: GenerationResponse | None) -> str:
    """Return the validated ``narrative`` string, or ``""`` when the reply is unusable.

    The reply must be a JSON object with a string ``narrative`` field. A non-JSON body, a missing
    field or a wrong type is discarded (returns ``""``); the caller then keeps the deterministic
    narrative rather than trusting the model.
    """
    if response is None or not response.text.strip():
        return ""
    try:
        parsed = json.loads(response.text)
    except (ValueError, TypeError):
        return ""
    if not isinstance(parsed, dict):
        return ""
    narrative = parsed.get("narrative")
    if not isinstance(narrative, str):
        return ""
    return narrative.strip()


def numbers_are_grounded(narrative: str, allowed: set[int]) -> bool:
    """True iff every integer in ``narrative`` appears in ``allowed`` (the engine's own numbers).

    The groundedness metric: a narrative may quote only figures the engine produced. Any other
    integer is a fabricated number and fails the check. Commas inside a figure are ignored so
    "1,000" matches 1000.
    """
    for match in _NUMBER.findall(narrative):
        value = int(match.replace(",", ""))
        if value not in allowed:
            return False
    return True
