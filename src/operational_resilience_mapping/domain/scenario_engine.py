"""ScenarioEngine: deterministic stay-within-tolerance scenario testing (slice 6).

Pure stdlib traversal. It removes a node (a vendor failure, a site loss, a platform outage),
propagates the disruption across the dependency graph deterministically, and compares the
computed disruption against the accepted MTD tolerance. Concentration-and-exit findings register
as aggravators: a removed node that is a LOCKED critical service has no exit path, so its
recovery is slower and the scenario is flagged. The model does nothing here; every number is the
engine's.
"""

from __future__ import annotations

from .kernel import Citation, Severity
from .models import (
    DependencyEdge,
    ResilienceMap,
    ScenarioKind,
    ScenarioResult,
)

#: Base recovery minutes for the removed node, by its own criticality. Deterministic data.
_BASE_RECOVERY: dict[Severity, int] = {
    Severity.CRITICAL: 480,
    Severity.HIGH: 240,
    Severity.MEDIUM: 120,
    Severity.LOW: 30,
}

#: Minutes added per dependency hop between the service and the removed node.
_HOP_PENALTY = 30

#: A node with no exit path (a LOCKED critical concentration finding) recovers this much slower.
_NO_EXIT_MULTIPLIER = 2


class ScenarioEngine:
    """Remove a node, propagate disruption, and compare it to the tolerance. Pure, testable."""

    def run(
        self,
        resilience_map: ResilienceMap,
        removed_node_id: str,
        mtd_tolerance: int,
        *,
        scenario_kind: ScenarioKind = ScenarioKind.VENDOR_FAILURE,
        name: str = "",
        aggravators_by_node: dict[str, tuple[str, ...]] | None = None,
        citations: tuple[Citation, ...] = (),
    ) -> ScenarioResult:
        """Return the stay-within-tolerance verdict for removing ``removed_node_id``."""
        aggravators_by_node = aggravators_by_node or {}
        node = resilience_map.node(removed_node_id)
        criticality = node.criticality if node is not None else Severity.MEDIUM

        impacted = self._impacted_ancestors(resilience_map.edges, removed_node_id)
        hops = self._hops(resilience_map.service.id, resilience_map.edges, removed_node_id)
        aggravators = aggravators_by_node.get(removed_node_id, ())

        base = _BASE_RECOVERY[criticality]
        hop_component = _HOP_PENALTY * max(hops - 1, 0)
        computed = base + hop_component
        if aggravators:
            computed *= _NO_EXIT_MULTIPLIER

        return ScenarioResult(
            name=name or f"{scenario_kind.value}:{removed_node_id}",
            scenario_kind=scenario_kind,
            removed_node_id=removed_node_id,
            service_id=resilience_map.service.id,
            computed_disruption=computed,
            tolerance=mtd_tolerance,
            within_tolerance=computed <= mtd_tolerance,
            impacted_node_ids=tuple(sorted(impacted)),
            aggravators=aggravators,
            citations=citations,
        )

    @staticmethod
    def _impacted_ancestors(edges: tuple[DependencyEdge, ...], target: str) -> set[str]:
        """Every node that depends (transitively) on ``target`` and so loses it (incl. service)."""
        reverse: dict[str, list[str]] = {}
        for edge in edges:
            reverse.setdefault(edge.target_id, []).append(edge.source_id)
        impacted: set[str] = set()
        stack = list(reverse.get(target, ()))
        while stack:
            current = stack.pop()
            if current in impacted:
                continue
            impacted.add(current)
            stack.extend(reverse.get(current, ()))
        return impacted

    @staticmethod
    def _hops(root: str, edges: tuple[DependencyEdge, ...], target: str) -> int:
        """Shortest number of dependency hops from ``root`` to ``target`` (0 if unreachable)."""
        forward: dict[str, list[str]] = {}
        for edge in edges:
            forward.setdefault(edge.source_id, []).append(edge.target_id)
        frontier = [(root, 0)]
        seen = {root}
        while frontier:
            current, depth = frontier.pop(0)
            if current == target:
                return depth
            for nxt in forward.get(current, ()):
                if nxt not in seen:
                    seen.add(nxt)
                    frontier.append((nxt, depth + 1))
        return 0
