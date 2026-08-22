"""ScenarioEngine: deterministic disruption propagation vs tolerance (slice 6)."""

from __future__ import annotations

from operational_resilience_mapping.domain.models import (
    ChainKind,
    DependencyEdge,
    DependencyNode,
    ImportantBusinessService,
    ResilienceMap,
    ScenarioKind,
    Severity,
)
from operational_resilience_mapping.domain.scenario_engine import ScenarioEngine

_SERVICE = ImportantBusinessService(id="ibs", name="Service", criticality=Severity.CRITICAL)


def _map() -> ResilienceMap:
    nodes = (
        DependencyNode(
            id="sys", kind=ChainKind.TECHNOLOGY, name="System", criticality=Severity.HIGH
        ),
        DependencyNode(
            id="vendor", kind=ChainKind.THIRD_PARTIES, name="Vendor", criticality=Severity.CRITICAL
        ),
    )
    edges = (DependencyEdge("ibs", "sys"), DependencyEdge("sys", "vendor"))
    return ResilienceMap(service=_SERVICE, nodes=nodes, edges=edges)


def test_removing_a_vendor_impacts_the_ancestors_that_depend_on_it() -> None:
    scenario = ScenarioEngine().run(_map(), "vendor", 100000)
    assert "sys" in scenario.impacted_node_ids
    assert "ibs" in scenario.impacted_node_ids


def test_within_tolerance_when_disruption_is_under_the_mtd() -> None:
    scenario = ScenarioEngine().run(_map(), "vendor", 100000)
    assert scenario.within_tolerance is True


def test_breach_when_disruption_exceeds_a_tight_mtd() -> None:
    scenario = ScenarioEngine().run(_map(), "vendor", 1)
    assert scenario.within_tolerance is False
    assert scenario.computed_disruption > scenario.tolerance


def test_an_aggravator_slows_recovery_and_can_flip_the_verdict() -> None:
    tight = 500
    clean = ScenarioEngine().run(_map(), "vendor", tight)
    aggravated = ScenarioEngine().run(
        _map(), "vendor", tight, aggravators_by_node={"vendor": ("locked, no exit path",)}
    )
    assert aggravated.computed_disruption > clean.computed_disruption
    assert aggravated.aggravators


def test_is_deterministic() -> None:
    first = ScenarioEngine().run(_map(), "vendor", 300, scenario_kind=ScenarioKind.VENDOR_FAILURE)
    second = ScenarioEngine().run(_map(), "vendor", 300, scenario_kind=ScenarioKind.VENDOR_FAILURE)
    assert first == second
