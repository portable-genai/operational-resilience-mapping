"""MapService: dedupe, orphan and cycle integrity are deterministic (slice 3)."""

from __future__ import annotations

from operational_resilience_mapping.domain.map_service import MapService
from operational_resilience_mapping.domain.models import (
    ChainKind,
    DependencyEdge,
    DependencyNode,
    GapKind,
    ImportantBusinessService,
    Severity,
)

_SERVICE = ImportantBusinessService(id="ibs", name="Service", criticality=Severity.CRITICAL)


def _node(node_id: str, kind: ChainKind = ChainKind.TECHNOLOGY) -> DependencyNode:
    return DependencyNode(id=node_id, kind=kind, name=node_id)


def test_a_clean_map_has_no_gaps_and_round_trips() -> None:
    nodes = [_node("a"), _node("b")]
    edges = [DependencyEdge("ibs", "a"), DependencyEdge("a", "b")]
    resilience_map, gaps = MapService().build(_SERVICE, nodes, edges)
    assert resilience_map.n_nodes == 2
    assert resilience_map.n_edges == 2
    assert gaps == []


def test_duplicate_nodes_and_edges_are_deduplicated() -> None:
    nodes = [_node("a"), _node("a")]
    edges = [DependencyEdge("ibs", "a"), DependencyEdge("ibs", "a")]
    resilience_map, gaps = MapService().build(_SERVICE, nodes, edges)
    assert resilience_map.n_nodes == 1
    assert resilience_map.n_edges == 1
    assert any(g.kind is GapKind.DUPLICATE for g in gaps)


def test_an_orphan_node_is_flagged() -> None:
    nodes = [_node("a"), _node("orphan")]
    edges = [DependencyEdge("ibs", "a")]
    _resilience_map, gaps = MapService().build(_SERVICE, nodes, edges)
    orphans = [g for g in gaps if g.kind is GapKind.ORPHAN]
    assert len(orphans) == 1
    assert orphans[0].ref == "orphan"


def test_a_dependency_cycle_is_detected() -> None:
    nodes = [_node("a"), _node("b")]
    edges = [
        DependencyEdge("ibs", "a"),
        DependencyEdge("a", "b"),
        DependencyEdge("b", "a"),
    ]
    _resilience_map, gaps = MapService().build(_SERVICE, nodes, edges)
    assert any(g.kind is GapKind.CYCLE for g in gaps)


def test_an_edge_to_an_unknown_node_is_flagged_and_dropped() -> None:
    nodes = [_node("a")]
    edges = [DependencyEdge("ibs", "a"), DependencyEdge("a", "ghost")]
    resilience_map, gaps = MapService().build(_SERVICE, nodes, edges)
    assert resilience_map.n_edges == 1
    assert any(g.kind is GapKind.UNMAPPED_ENDPOINT for g in gaps)


def test_build_is_deterministic() -> None:
    nodes = [_node("a"), _node("b")]
    edges = [DependencyEdge("ibs", "a"), DependencyEdge("a", "b")]
    first, first_gaps = MapService().build(_SERVICE, list(nodes), list(edges))
    second, second_gaps = MapService().build(_SERVICE, list(nodes), list(edges))
    assert first.nodes == second.nodes
    assert first.edges == second.edges
    assert first_gaps == second_gaps
