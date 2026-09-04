"""IngestionService: deterministic multi-source dependency reconciliation (slice 4).

Pure stdlib. It turns the three ingestion sources into typed dependency nodes:

* technology dependencies from the asset-inventory port (:class:`ResourceConfig`); * third parties
  from third-party-risk-ddq's outsourcing register over A2A (:class:`ThirdPartyArrangement`); *
  process/people/facilities nodes extracted from documents (:class:`ExtractedDocument`).

The model proposes candidate dependency edges with citations; this engine deterministically
reconciles them against the known nodes: it accepts only schema-valid edges (both endpoints
known), deduplicates, and flags conflicts (an unmapped endpoint) and duplicates as gaps. The
model never mutates the graph; a candidate it cannot ground becomes a gap, never a silent edge.
"""

from __future__ import annotations

from .kernel import Citation, Severity
from .models import (
    CandidateEdge,
    ChainKind,
    DependencyEdge,
    DependencyNode,
    ExtractedDocument,
    GapKind,
    Reconciliation,
    ReconciliationGap,
    ResourceConfig,
    ThirdPartyArrangement,
)


class IngestionService:
    """Normalise ingestion sources into nodes and reconcile model-proposed edges. Pure."""

    @staticmethod
    def nodes_from_resources(resources: list[ResourceConfig]) -> list[DependencyNode]:
        """Technology dependency nodes from the asset inventory."""
        return [
            DependencyNode(
                id=resource.id,
                kind=ChainKind.TECHNOLOGY,
                name=resource.name,
                criticality=resource.criticality,
                provider=resource.provider,
                region=resource.region,
            )
            for resource in resources
        ]

    @staticmethod
    def nodes_from_arrangements(
        arrangements: list[ThirdPartyArrangement],
    ) -> list[DependencyNode]:
        """Third-party dependency nodes from third-party-risk-ddq's register."""
        return [
            DependencyNode(
                id=arrangement.id,
                kind=ChainKind.THIRD_PARTIES,
                name=arrangement.vendor_name,
                criticality=arrangement.criticality,
                region=arrangement.region,
                tenant=arrangement.tenant,
            )
            for arrangement in arrangements
        ]

    @staticmethod
    def nodes_from_documents(
        documents: list[ExtractedDocument],
        *,
        kind: ChainKind = ChainKind.PROCESS,
    ) -> list[DependencyNode]:
        """Process / people / facilities nodes extracted from source documents."""
        out: list[DependencyNode] = []
        for document in documents:
            name = document.field("name") or document.document_id
            out.append(
                DependencyNode(
                    id=document.document_id,
                    kind=kind,
                    name=name,
                    criticality=_severity_or_default(document.field("criticality")),
                )
            )
        return out

    def reconcile(
        self,
        known_node_ids: set[str],
        candidates: list[CandidateEdge],
    ) -> Reconciliation:
        """Accept schema-valid, deduplicated edges; flag conflicts and duplicates as gaps."""
        accepted: list[DependencyEdge] = []
        gaps: list[ReconciliationGap] = []
        seen: set[tuple[str, str]] = set()

        for candidate in candidates:
            key = (candidate.source_id, candidate.target_id)
            citations = (candidate.citation,) if candidate.citation is not None else ()
            if candidate.source_id not in known_node_ids or (
                candidate.target_id not in known_node_ids
            ):
                gaps.append(
                    ReconciliationGap(
                        kind=GapKind.UNMAPPED_ENDPOINT,
                        detail=(
                            f"model proposed {candidate.source_id} -> {candidate.target_id} but "
                            "an endpoint is not a known node; recorded as a gap, not an edge"
                        ),
                        ref=f"{candidate.source_id}->{candidate.target_id}",
                        citations=_only_citations(citations),
                    )
                )
                continue
            if key in seen:
                gaps.append(
                    ReconciliationGap(
                        kind=GapKind.DUPLICATE,
                        detail=(
                            f"duplicate proposed edge {candidate.source_id} -> "
                            f"{candidate.target_id} dropped"
                        ),
                        ref=f"{candidate.source_id}->{candidate.target_id}",
                    )
                )
                continue
            seen.add(key)
            accepted.append(
                DependencyEdge(
                    source_id=candidate.source_id,
                    target_id=candidate.target_id,
                    criticality=candidate.criticality,
                    rationale=f"reconciled {candidate.kind.value} dependency",
                    citations=_only_citations(citations),
                )
            )
        return Reconciliation(accepted=tuple(accepted), gaps=tuple(gaps))


def _only_citations(citations: tuple[Citation | None, ...]) -> tuple[Citation, ...]:
    return tuple(c for c in citations if c is not None)


def _severity_or_default(raw: str) -> Severity:
    if not raw:
        return Severity.MEDIUM
    try:
        return Severity(raw.lower())
    except ValueError:
        return Severity.MEDIUM
