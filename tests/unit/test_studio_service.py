"""StudioService: the end-to-end pipeline on the offline profile (slices 3 to 7)."""

from __future__ import annotations

from operational_resilience_mapping.config import build_container
from operational_resilience_mapping.domain.models import (
    Regulator,
    ScenarioKind,
    ToleranceMetric,
)
from operational_resilience_mapping.domain.studio_service import StudioService
from operational_resilience_mapping.factory import build_studio

from tests.conftest import local_settings
from tests.fixtures import sample_cases


def _studio() -> StudioService:
    return build_studio(build_container(local_settings()))


def test_build_map_ingests_all_three_sources_and_persists() -> None:
    studio = _studio()
    resilience_map, reconciliation, _gaps = studio.build_map(
        sample_cases.SERVICE,
        sample_cases.SCOPE,
        actor=sample_cases.ACTOR,
        document_ids=("doc-settlement-runbook",),
    )
    kinds = {n.kind.value for n in resilience_map.nodes}
    assert "technology" in kinds
    assert "third_parties" in kinds
    assert "process" in kinds
    assert reconciliation.accepted, "the reconciler accepted no edges"


def test_the_stored_map_round_trips() -> None:
    studio = _studio()
    resilience_map, _r, _g = studio.build_map(
        sample_cases.SERVICE, sample_cases.SCOPE, actor=sample_cases.ACTOR
    )
    fetched = studio.get_map(sample_cases.SERVICE.id)
    assert fetched is not None
    assert fetched.service.id == resilience_map.service.id


def test_propose_tolerances_derives_numbers_and_routes() -> None:
    studio = _studio()
    resilience_map, _r, _g = studio.build_map(
        sample_cases.SERVICE, sample_cases.SCOPE, actor=sample_cases.ACTOR
    )
    proposal, review_ref = studio.propose_tolerances(
        sample_cases.SERVICE, resilience_map, Regulator.APRA_CPS230, actor=sample_cases.ACTOR
    )
    assert {t.metric for t in proposal.tolerances} == set(ToleranceMetric)
    assert proposal.requires_human_review is True
    assert review_ref, "a tolerance proposal must be routed to human review (rule R8)"
    assert proposal.citations, "tolerances must be grounded on the compliance citations"


def test_the_narrative_is_grounded_and_adds_no_number() -> None:
    studio = _studio()
    resilience_map, _r, _g = studio.build_map(
        sample_cases.SERVICE, sample_cases.SCOPE, actor=sample_cases.ACTOR
    )
    proposal, _ref = studio.propose_tolerances(
        sample_cases.SERVICE, resilience_map, Regulator.APRA_CPS230, actor=sample_cases.ACTOR
    )
    # The offline stub narrative carries no figures, so it can invent none.
    assert not any(ch.isdigit() for ch in proposal.narrative)


def test_concentration_finds_single_region_on_the_fixture_estate() -> None:
    findings = _studio().concentration(sample_cases.SCOPE)
    dimensions = {f.dimension.value for f in findings}
    # The fixture estate is all in one region, so the single-region concentration must fire.
    assert "single_region" in dimensions
    for finding in findings:
        assert finding.citations, "a concentration finding must be grounded"


def test_a_locked_critical_vendor_failure_breaches_a_tight_tolerance() -> None:
    studio = _studio()
    resilience_map, _r, _g = studio.build_map(
        sample_cases.SERVICE, sample_cases.SCOPE, actor=sample_cases.ACTOR
    )
    proposal, _ref = studio.propose_tolerances(
        sample_cases.SERVICE, resilience_map, Regulator.APRA_CPS230, actor=sample_cases.ACTOR
    )
    scenario, review_ref = studio.run_scenario(
        resilience_map,
        "svc-fraud-scorer",
        list(proposal.tolerances),
        actor=sample_cases.ACTOR,
        scope=sample_cases.SCOPE,
        scenario_kind=ScenarioKind.VENDOR_FAILURE,
    )
    assert scenario.aggravators, "a LOCKED critical service failure should register an aggravator"
    assert not scenario.within_tolerance
    assert review_ref, "a breached scenario must be routed to human review"
