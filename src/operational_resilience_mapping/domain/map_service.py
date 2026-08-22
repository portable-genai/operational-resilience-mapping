"""MapService: deterministic resilience-map integrity (slice 3).

Pure stdlib. Given an important business service, its dependency nodes and its edges, it owns
graph integrity: it deduplicates nodes and edges, detects orphan nodes the service cannot reach,
and detects dependency cycles. The result is a normalised :class:`ResilienceMap` plus the
integrity gaps, both a deterministic function of the inputs (there is no clock beyond the map's
own ``generated_at``), so a stored map round-trips byte-identical.
"""

from __future__ import annotations

from .models import (
    DependencyEdge,
    DependencyNode,
    GapKind,
    ImportantBusinessService,
    ReconciliationGap,
    ResilienceMap,
)


class MapService:
    """Normalise a resilience map and report its integrity gaps. Pure, testable."""

    def build(
        self,
        service: ImportantBusinessService,
        nodes: list[DependencyNode],
        edges: list[DependencyEdge],
    ) -> tuple[ResilienceMap, list[ReconciliationGap]]:
        """Return the normalised map and its integrity gaps (orphans, cycles)."""
        unique_nodes = self._dedupe_nodes(nodes)
        known = {service.id} | {n.id for n in unique_nodes}
        unique_edges, edge_gaps = self._dedupe_edges(edges, known)

        reachable = self._reachable_from(service.id, unique_edges)
        gaps = list(edge_gaps)
        gaps.extend(self._orphans(unique_nodes, reachable))
        gaps.extend(self._cycles(service.id, unique_nodes, unique_edges))

        resilience_map = ResilienceMap(
            service=service,
            nodes=tuple(unique_nodes),
            edges=tuple(unique_edges),
        )
        return resilience_map, gaps

    @staticmethod
    def _dedupe_nodes(nodes: list[DependencyNode]) -> list[DependencyNode]:
        seen: set[str] = set()
        out: list[DependencyNode] = []
        for node in nodes:
            if node.id in seen:
                continue
            seen.add(node.id)
            out.append(node)
        return out

    @staticmethod
    def _dedupe_edges(
        edges: list[DependencyEdge],
        known: set[str],
    ) -> tuple[list[DependencyEdge], list[ReconciliationGap]]:
        seen: set[tuple[str, str]] = set()
        out: list[DependencyEdge] = []
        gaps: list[ReconciliationGap] = []
        for edge in edges:
            key = (edge.source_id, edge.target_id)
            if key in seen:
                gaps.append(
                    ReconciliationGap(
                        kind=GapKind.DUPLICATE,
                        detail=f"duplicate edge {edge.source_id} -> {edge.target_id} dropped",
                        ref=f"{edge.source_id}->{edge.target_id}",
                    )
                )
                continue
            if edge.source_id not in known or edge.target_id not in known:
                gaps.append(
                    ReconciliationGap(
                        kind=GapKind.UNMAPPED_ENDPOINT,
                        detail=(
                            f"edge {edge.source_id} -> {edge.target_id} references a node that "
                            "is not in the map; dropped"
                        ),
                        ref=f"{edge.source_id}->{edge.target_id}",
                    )
                )
                continue
            seen.add(key)
            out.append(edge)
        return out, gaps

    @staticmethod
    def _adjacency(edges: list[DependencyEdge]) -> dict[str, list[str]]:
        adjacency: dict[str, list[str]] = {}
        for edge in edges:
            adjacency.setdefault(edge.source_id, []).append(edge.target_id)
        return adjacency

    @classmethod
    def _reachable_from(cls, root: str, edges: list[DependencyEdge]) -> set[str]:
        adjacency = cls._adjacency(edges)
        seen: set[str] = set()
        stack = [root]
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            stack.extend(adjacency.get(current, ()))
        return seen

    @staticmethod
    def _orphans(
        nodes: list[DependencyNode],
        reachable: set[str],
    ) -> list[ReconciliationGap]:
        return [
            ReconciliationGap(
                kind=GapKind.ORPHAN,
                detail=(
                    f"node '{node.name}' ({node.id}) is not reachable from the business "
                    "service; it maps to no dependency chain"
                ),
                ref=node.id,
            )
            for node in nodes
            if node.id not in reachable
        ]

    @classmethod
    def _cycles(
        cls,
        root: str,
        nodes: list[DependencyNode],
        edges: list[DependencyEdge],
    ) -> list[ReconciliationGap]:
        adjacency = cls._adjacency(edges)
        colour: dict[str, int] = {}  # 0=visiting, 1=done
        gaps: list[ReconciliationGap] = []
        starts = [root, *(n.id for n in nodes)]

        def visit(node: str, stack: list[str]) -> None:
            colour[node] = 0
            for target in adjacency.get(node, ()):
                if colour.get(target) == 0:
                    gaps.append(
                        ReconciliationGap(
                            kind=GapKind.CYCLE,
                            detail=(
                                "dependency cycle detected: "
                                + " -> ".join([*stack[stack.index(target) :], node, target])
                            ),
                            ref=f"{node}->{target}",
                        )
                    )
                elif target not in colour:
                    visit(target, [*stack, target])
            colour[node] = 1

        for start in starts:
            if start not in colour:
                visit(start, [start])
        return gaps
