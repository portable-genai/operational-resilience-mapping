"""The pii_safety metric the GATE SHIPS is proved able to go red (check E2).

This file used to score a four-line helper defined three lines above the assertion, and the gate
shipped NO pii_safety metric at all: SPEC.md promised one, docs/practices-audit.md recorded it as
PASS, and `eval/run_eval.py` scored four metrics, none of them this. So the falsification was
green, the documentation was confident, and nothing was measuring the boundary. Meanwhile the
tolerance path was sending a client-supplied service name to the model verbatim.

The metric now exists, and the falsification runs against `run_eval` itself, imported as the gate
imports it. The mutants are the two shapes the metric exists to catch: an identifier that survives
into the model prompt, and one that survives into the WORM record's citations while the summary
beside it is clean.
"""

from __future__ import annotations

from typing import Any

import run_eval as ev
from agent_eval_kit import assert_can_go_red

from tests.fixtures import sample_cases

_PLANTED = (sample_cases.PLANTED_NRIC, sample_cases.PLANTED_EMAIL)

#: What the studio hands the generation port. The engine figures are the same in both; only the
#: client-supplied service name differs, which is exactly the field that was crossing unmasked.
_CLEAN_PROMPT = (
    "Service: Retail Payments owner NRIC [REDACTED:SG_NRIC_FIN] (FICTIONAL). "
    "Engine-derived tolerances: MTD 120 minutes."
)
_LEAKY_PROMPT = (
    f"Service: Retail Payments owner NRIC {sample_cases.PLANTED_NRIC} (FICTIONAL). "
    "Engine-derived tolerances: MTD 120 minutes."
)

#: One audit row as the WORM store hands it back. The summary is CLEAN in both: the summary was
#: never the field that leaked, so a metric that only reads it scores these two identically.
_CLEAN_ROW: dict[str, Any] = {
    "action": "propose_tolerances",
    "actor": sample_cases.ACTOR,
    "redacted_summary": "Retail Payments (FICTIONAL): proposed 4 impact tolerances",
    "citations": [
        {
            "source_id": "rsk1:answer:[REDACTED:SG_NRIC_FIN]",
            "title": "Requirement raised by [REDACTED:EMAIL_ADDRESS]",
            "snippet": "owner NRIC [REDACTED:SG_NRIC_FIN] must set the tolerance",
        }
    ],
}
_LEAKY_ROW: dict[str, Any] = {
    **_CLEAN_ROW,
    "citations": [
        {
            "source_id": f"rsk1:answer:{sample_cases.PLANTED_NRIC}",
            "title": f"Requirement raised by {sample_cases.PLANTED_EMAIL}",
            "snippet": f"owner NRIC {sample_cases.PLANTED_NRIC} must set the tolerance",
        }
    ],
}


def _score_prompt(prompts: list[str]) -> float:
    """The gate's own scorer over the model boundary. No re-implementation here."""
    return ev.pii_safety(prompts, _PLANTED)


def _score_rows(rows: list[dict[str, Any]]) -> float:
    """The gate's own scorer over the gate's own audit-field selection."""
    return ev.pii_safety(ev.audit_texts(rows), _PLANTED)


def test_pii_safety_can_go_red_on_the_model_boundary() -> None:
    assert_can_go_red(
        _score_prompt,
        green=[_CLEAN_PROMPT],
        red=[_LEAKY_PROMPT],
        threshold=ev.THRESHOLDS["pii_safety"],
        metric="pii_safety",
    )


def test_pii_safety_can_go_red_on_the_audit_boundary() -> None:
    assert_can_go_red(
        _score_rows,
        green=[_CLEAN_ROW],
        red=[_LEAKY_ROW],
        threshold=ev.THRESHOLDS["pii_safety"],
        metric="pii_safety",
    )


def test_pii_safety_is_green_over_a_real_run_of_the_golden_set() -> None:
    """Green, and green over the REAL studio rather than over an empty list of nothing."""
    crossed, planted = ev.crossing_texts(ev._load(ev.DEFAULT_DATASET))
    assert planted, "the golden set plants no identifier, so the metric can never go red on it"
    assert any("[REDACTED:" in text for text in crossed), (
        "the scan found no redaction marker, so it is reading places nothing crosses and its "
        "green means nothing"
    )
    assert ev.pii_safety(crossed, planted) == 1.0


def test_the_scan_excludes_the_actor_so_it_can_ever_be_green() -> None:
    """The caveat, pinned: widening this to whole rows makes the metric permanently red.

    ``actor`` is the verified principal and is an address by design. A well-meaning "scan the
    whole record" change would make every run fail on the attribution column, and the next
    person would relax the threshold rather than narrow the scan.
    """
    row: dict[str, Any] = {**_CLEAN_ROW, "actor": "analyst@bank.example"}
    assert ev.pii_safety(ev.audit_texts([row]), _PLANTED) == 1.0
