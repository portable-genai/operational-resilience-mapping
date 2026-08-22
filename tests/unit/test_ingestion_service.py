"""IngestionService: deterministic reconciliation of model-proposed edges (slice 4)."""

from __future__ import annotations

from operational_resilience_mapping.domain.ingestion_service import IngestionService
from operational_resilience_mapping.domain.kernel import Citation, Severity
from operational_resilience_mapping.domain.models import (
    CandidateEdge,
    ChainKind,
    GapKind,
    ResourceConfig,
    ThirdPartyArrangement,
)


def test_resources_become_technology_nodes() -> None:
    nodes = IngestionService().nodes_from_resources(
        [ResourceConfig(id="r", kind="db", name="DB", criticality=Severity.HIGH)]
    )
    assert nodes[0].kind is ChainKind.TECHNOLOGY
    assert nodes[0].criticality is Severity.HIGH


def test_arrangements_become_third_party_nodes() -> None:
    nodes = IngestionService().nodes_from_arrangements(
        [ThirdPartyArrangement(id="tp", vendor_name="Vendor", service="svc")]
    )
    assert nodes[0].kind is ChainKind.THIRD_PARTIES
    assert nodes[0].name == "Vendor"


def test_a_valid_candidate_edge_is_accepted() -> None:
    result = IngestionService().reconcile(
        {"a", "b"},
        [CandidateEdge("a", "b", ChainKind.TECHNOLOGY, Severity.HIGH, Citation("s", "t"))],
    )
    assert len(result.accepted) == 1
    assert result.accepted[0].citations, "an accepted edge keeps its grounding citation"
    assert result.gaps == ()


def test_an_edge_to_an_unknown_endpoint_becomes_a_gap_not_an_edge() -> None:
    result = IngestionService().reconcile(
        {"a"},
        [CandidateEdge("a", "ghost", ChainKind.TECHNOLOGY)],
    )
    assert result.accepted == ()
    assert result.gaps[0].kind is GapKind.UNMAPPED_ENDPOINT


def test_a_duplicate_candidate_edge_is_dropped() -> None:
    result = IngestionService().reconcile(
        {"a", "b"},
        [CandidateEdge("a", "b", ChainKind.TECHNOLOGY), CandidateEdge("a", "b", ChainKind.DATA)],
    )
    assert len(result.accepted) == 1
    assert any(g.kind is GapKind.DUPLICATE for g in result.gaps)
