"""Every boundary the studio crosses is redacted, not only the audit summary (check C3).

Three sinks take content out of this process, and they fail independently:

* the MODEL. ``_narrate_tolerances`` builds its prompt from ``service.name``, which arrives
  verbatim in the ``POST /v1/tolerance`` body. The redaction guard sat downstream of this call,
  so the identifier reached the bound generation adapter and, under the ``gcp`` profile, Gemini.
* the WORM RECORD. The summary was masked and the citations beside it were not, so anything a
  citation carried was persisted verbatim in an immutable, long-retained store.
* the REVIEW CONSOLE. ``_kit_citations`` masked the snippet and left the locator and the title
  raw, and a locator is routinely built from client text.

The scan covers the CONTENT fields. ``actor`` is the verified principal and is an address by
design, so a blanket scan over a whole audit row could never go green, and masking the actor
would erase the only column that says who acted.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import pytest
from pii_kit import pack_leak

import operational_resilience_mapping.domain.studio_service as studio_service
from operational_resilience_mapping.adapters._review_payload import result_to_review
from operational_resilience_mapping.adapters.local.audit import LocalAuditAdapter
from operational_resilience_mapping.config import Container
from operational_resilience_mapping.domain.models import Regulator
from operational_resilience_mapping.domain.pii import PII_PATTERNS
from operational_resilience_mapping.domain.studio_service import StudioService

from tests.fixtures import sample_cases

_PLANTED = (sample_cases.PLANTED_NRIC, sample_cases.PLANTED_EMAIL)


def _content(row: Mapping[str, Any]) -> str:
    """Every content-bearing field of one audit row. Attribution is excluded on purpose."""
    return " ".join(
        (
            str(row.get("redacted_summary", "")),
            json.dumps(row.get("citations", []), sort_keys=True),
        )
    )


def _assert_clean(blob: str, where: str) -> None:
    assert not pack_leak(blob, PII_PATTERNS), f"pack row matched at {where}: {blob}"
    for token in _PLANTED:
        assert token not in blob, f"planted {token!r} reached {where}: {blob}"


@pytest.fixture()
def prompts(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Tap the real model boundary: every prompt the studio hands the generation port."""
    seen: list[str] = []
    original = studio_service.build_request

    def _spy(system_instruction: str, prompt: str) -> Any:
        seen.append(prompt)
        return original(system_instruction, prompt)

    monkeypatch.setattr(studio_service, "build_request", _spy)
    return seen


def _propose(studio: StudioService) -> Any:
    resilience_map, _reconciliation, _gaps = studio.build_map(
        sample_cases.PII_SERVICE,
        sample_cases.SCOPE,
        actor=sample_cases.ACTOR,
        tenant=sample_cases.TENANT,
    )
    return studio.propose_tolerances(
        sample_cases.PII_SERVICE,
        resilience_map,
        Regulator.APRA_CPS230,
        actor=sample_cases.ACTOR,
        tenant=sample_cases.TENANT,
    )


def test_no_identifier_reaches_the_model(studio: StudioService, prompts: list[str]) -> None:
    _propose(studio)
    assert prompts, "the tolerance path called no model, so this proves nothing"
    for prompt in prompts:
        _assert_clean(prompt, "the model prompt")


def test_no_identifier_reaches_the_audit_record(
    studio: StudioService, container: Container
) -> None:
    _propose(studio)

    audit = container.audit
    assert isinstance(audit, LocalAuditAdapter)
    rows = list(audit.log.read_all())
    assert rows, "the tolerance path wrote no audit record, so this proves nothing"
    for row in rows:
        _assert_clean(_content(row), "the WORM record")


def test_the_worm_boundary_holds_for_a_citation_that_carries_client_text(
    container: Container,
) -> None:
    """The offline citations are static regulatory references. The boundary must not rely on that.

    The managed compliance adapter reads compliance-advisory over the wire and the ingestion path
    builds a
    locator from a document field, so a citation is only safe by accident today. This drives the
    REAL audit adapter with an compliance-advisory-shaped citation whose locator, title and snippet
    all carry
    client text, and requires the stored record to be clean.
    """
    from operational_resilience_mapping.domain.kernel import AuditEvent, Decision, Severity

    audit = container.audit
    assert isinstance(audit, LocalAuditAdapter)
    audit.record(
        AuditEvent(
            action="propose_tolerances",
            actor=sample_cases.ACTOR,
            decision=Decision.ESCALATED,
            severity=Severity.CRITICAL,
            redacted_summary="Retail Payments (FICTIONAL): proposed 4 impact tolerances",
            citations=(sample_cases.PII_CITATION,),
        )
    )
    rows = list(audit.log.read_all())
    assert rows
    for row in rows:
        _assert_clean(_content(row), "the WORM record")


def test_no_identifier_reaches_the_review_console() -> None:
    """Including the citation LOCATOR and TITLE, which cross the wire like a snippet does."""
    review = result_to_review(
        sample_cases.PII_REVIEW, maker=sample_cases.ACTOR, tenant=sample_cases.TENANT
    )
    blob = json.dumps(
        {
            "subject": review.subject,
            "summary": review.summary,
            "case_ref": review.case_ref,
            "source_key": review.source_key,
            "citations": [
                {"source_id": c.source_id, "title": c.title, "snippet": c.snippet}
                for c in review.citations
            ],
        },
        sort_keys=True,
    )
    _assert_clean(blob, "the human-review-console review payload")


def test_the_actor_is_kept_verbatim_because_it_is_attribution(
    studio: StudioService, container: Container
) -> None:
    """The caveat, pinned: the principal is an address and must NOT be masked away."""
    _propose(studio)

    audit = container.audit
    assert isinstance(audit, LocalAuditAdapter)
    actors = {str(row.get("actor", "")) for row in audit.log.read_all()}
    assert actors == {sample_cases.ACTOR}
