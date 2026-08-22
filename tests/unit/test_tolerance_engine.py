"""ToleranceEngine: deterministic per-regulator tolerance derivation (slice 5).

The independent oracle re-derives the expected values straight from the SAME packs the engine
uses, but by a separate path (a direct dict lookup at the chain criticality), so a bug in the
engine's derivation shows up as a mismatch. The provable-red test perturbs a pack and asserts the
metric moves.
"""

from __future__ import annotations

from operational_resilience_mapping.domain.models import (
    ChainKind,
    DependencyNode,
    ImportantBusinessService,
    Regulator,
    ResilienceMap,
    Severity,
    ToleranceMetric,
)
from operational_resilience_mapping.domain.tolerance_engine import TOLERANCE_PACKS, ToleranceEngine


def _map(service: ImportantBusinessService, node_criticality: Severity) -> ResilienceMap:
    node = DependencyNode(id="n", kind=ChainKind.TECHNOLOGY, name="n", criticality=node_criticality)
    return ResilienceMap(service=service, nodes=(node,), edges=())


def test_chain_criticality_is_the_worst_of_service_and_nodes() -> None:
    service = ImportantBusinessService(id="s", name="s", criticality=Severity.MEDIUM)
    resilience_map = _map(service, Severity.CRITICAL)
    assert ToleranceEngine().chain_criticality(service, resilience_map) is Severity.CRITICAL


def test_every_regulator_derives_the_four_metrics_matching_its_pack() -> None:
    service = ImportantBusinessService(id="s", name="s", criticality=Severity.HIGH)
    resilience_map = _map(service, Severity.HIGH)
    for regulator in Regulator:
        pack = TOLERANCE_PACKS[regulator]
        tolerances = ToleranceEngine().derive(service, resilience_map, regulator)
        by_metric = {t.metric: t.value for t in tolerances}
        # Independent oracle: direct pack lookup at chain criticality HIGH.
        expected_mtd = pack.mtd_by_criticality[Severity.HIGH]
        assert by_metric[ToleranceMetric.MTD] == expected_mtd
        assert by_metric[ToleranceMetric.RPO] == pack.rpo_by_criticality[Severity.HIGH]
        assert by_metric[ToleranceMetric.HARM_THRESHOLD] == pack.harm_by_criticality[Severity.HIGH]
        expected_rto = expected_mtd * pack.rto_numerator // pack.rto_denominator
        assert by_metric[ToleranceMetric.RTO] == expected_rto


def test_a_stricter_chain_criticality_tightens_the_mtd() -> None:
    service = ImportantBusinessService(id="s", name="s", criticality=Severity.LOW)
    loose = ToleranceEngine().derive(service, _map(service, Severity.LOW), Regulator.APRA_CPS230)
    strict = ToleranceEngine().derive(
        service, _map(service, Severity.CRITICAL), Regulator.APRA_CPS230
    )
    loose_mtd = next(t.value for t in loose if t.metric is ToleranceMetric.MTD)
    strict_mtd = next(t.value for t in strict if t.metric is ToleranceMetric.MTD)
    assert strict_mtd < loose_mtd


def test_the_metric_can_go_red_when_a_pack_value_changes() -> None:
    """A tolerance metric that could not move if the pack changed would not be a real check."""
    service = ImportantBusinessService(id="s", name="s", criticality=Severity.CRITICAL)
    resilience_map = _map(service, Severity.CRITICAL)
    baseline = ToleranceEngine().derive(service, resilience_map, Regulator.APRA_CPS230)
    baseline_mtd = next(t.value for t in baseline if t.metric is ToleranceMetric.MTD)

    from dataclasses import replace

    tampered_pack = dict(TOLERANCE_PACKS)
    original = tampered_pack[Regulator.APRA_CPS230]
    current = original.mtd_by_criticality[Severity.CRITICAL]
    bumped = original.mtd_by_criticality | {Severity.CRITICAL: current + 1}
    tampered_pack[Regulator.APRA_CPS230] = replace(original, mtd_by_criticality=bumped)
    tampered = ToleranceEngine(tampered_pack).derive(service, resilience_map, Regulator.APRA_CPS230)
    tampered_mtd = next(t.value for t in tampered if t.metric is ToleranceMetric.MTD)
    assert tampered_mtd != baseline_mtd
