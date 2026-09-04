"""Rule R8: an escalated result is ROUTED to human-review-console, not left in a per-repo boolean.

This is the standing gate for the failure the rule exists to prevent. A repo can set
``requires_human_review = True``, pass every other test, and still auto-execute in practice
because nothing ever reads the flag. So the assertions here are about the ROUTING, not the flag:
a consequential result produces an outbound review, a within-tolerance scenario produces none,
the payload leaves redacted, and the on-prem placeholder refuses rather than swallowing it.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from operational_resilience_mapping.adapters.gcp.review_router import (
    CloudReviewRouter,
)
from operational_resilience_mapping.adapters.local.review_router import (
    LocalReviewRouter,
)
from operational_resilience_mapping.adapters.onprem.review_router import (
    OnPremReviewRouter,
)
from operational_resilience_mapping.api.app import (
    app,
)
from operational_resilience_mapping.config import (
    Settings,
    build_container,
)
from operational_resilience_mapping.domain.kernel import (
    Severity,
)
from operational_resilience_mapping.domain.models import (
    ImpactTolerance,
    Regulator,
    ScenarioKind,
    ToleranceMetric,
)
from operational_resilience_mapping.factory import (
    build_studio,
)

from tests.conftest import local_settings
from tests.fixtures import sample_cases


def _settings(profile: str = "local") -> Settings:
    return Settings(profile=profile, audit_path=":memory:", tenant="demo-bank")


def test_an_escalated_result_produces_an_outbound_review() -> None:
    router = LocalReviewRouter(_settings())
    ref = router.route(sample_cases.ESCALATING_REVIEW, maker="analyst@bank.example")
    assert ref, "routing must return a reference, so the caller can record where it went"
    pending = router.outbox.pending()
    assert len(pending) == 1
    review = pending[0].review
    assert review.maker == "analyst@bank.example"
    assert review.tenant == "demo-bank"
    assert review.severity == Severity.CRITICAL.value
    assert review.source_key, "a durable outbox needs an idempotency key"


def test_a_critical_result_demands_dual_control() -> None:
    router = LocalReviewRouter(_settings())
    router.route(sample_cases.ESCALATING_REVIEW, maker="analyst@bank.example")
    assert router.outbox.pending()[0].review.required_approvals == 2


def test_the_payload_is_redacted_before_it_leaves_the_process() -> None:
    """human-review-console is a shared sink; a raw identifier must never reach the wire."""
    router = LocalReviewRouter(_settings())
    router.route(sample_cases.PII_REVIEW, maker="analyst@bank.example")
    review = router.outbox.pending()[0].review
    wire = repr(review.to_payload())
    assert sample_cases.PLANTED_NRIC not in wire
    assert "REDACTED" in wire


def test_the_managed_router_refuses_when_no_console_is_configured() -> None:
    """An escalation with nowhere to go must fail loudly, not return as if it were reviewed."""
    router = CloudReviewRouter(Settings(profile="gcp", audit_path=":memory:", review_url=""))
    with pytest.raises(RuntimeError, match="R8"):
        router.route(sample_cases.ESCALATING_REVIEW, maker="analyst@bank.example")


def test_the_onprem_placeholder_refuses_rather_than_dropping_the_escalation() -> None:
    router = OnPremReviewRouter(_settings("onprem"))
    with pytest.raises(NotImplementedError, match="R8"):
        router.route(sample_cases.ESCALATING_REVIEW, maker="analyst@bank.example")


def test_the_api_routes_the_tolerance_proposal_in_the_same_request() -> None:
    """The serving path, not just the adapter: an escalation must not depend on a later job."""
    client = TestClient(app, client=("127.0.0.1", 50000))
    proposed = client.post(
        "/v1/tolerance",
        json={
            "scope": sample_cases.SCOPE,
            "service_id": sample_cases.SERVICE.id,
            "service_name": sample_cases.SERVICE.name,
            "regulator": "APRA_CPS230",
        },
        headers={"X-Dev-Persona": "auditor"},
    ).json()
    assert proposed["requires_human_review"] is True
    assert proposed["review_ref"], "a tolerance proposal with no routing reference went nowhere"


def test_a_within_tolerance_scenario_manufactures_no_review() -> None:
    """The studio must not route a scenario that stays within tolerance (no phantom escalation)."""
    studio = build_studio(build_container(local_settings()))
    resilience_map, _reconciliation, _gaps = studio.build_map(
        sample_cases.SERVICE, sample_cases.SCOPE, actor=sample_cases.ACTOR
    )
    generous = [
        ImpactTolerance(
            service_id=sample_cases.SERVICE.id,
            metric=ToleranceMetric.MTD,
            value=1_000_000,
            unit="minutes",
            regulator=Regulator.APRA_CPS230,
            basis="test",
        )
    ]
    scenario, review_ref = studio.run_scenario(
        resilience_map,
        "tp-kyc-bureau",
        generous,
        actor=sample_cases.ACTOR,
        scope=sample_cases.SCOPE,
        scenario_kind=ScenarioKind.VENDOR_FAILURE,
    )
    assert scenario.within_tolerance is True
    assert review_ref == "", "a within-tolerance scenario must not manufacture a review"
