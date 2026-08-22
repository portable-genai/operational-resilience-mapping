"""Vertical artifact models: the Operational Resilience Studio's own request and result types.

The artifacts THIS vertical produces, as opposed to the vertical-neutral machinery in
``kernel.py``. Everything here is pure stdlib: no web framework, no cloud SDK. The service's own
name is deliberately kept out of this docstring so a rendered line's length never depends on
``friendly_name``.

The studio builds a resilience map for an important business service (the dependency chain across
people, process, technology, facilities, third parties and data), proposes impact tolerances per
regulator, and tests stay-within-tolerance under a failure scenario. Every consequential number
comes from a pure engine; the model narrates only. ``ResilienceReview`` is the consequential
result routed to Hrz7 under rule R8.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from hex_service_kit.enums import LenientStrEnum

from .kernel import Citation, Decision, Severity, utcnow

# --------------------------------------------------------------------------- #
# Taxonomies
# --------------------------------------------------------------------------- #


class Regulator(LenientStrEnum):
    """Operational-resilience regimes whose impact-tolerance parameter shapes the studio carries."""

    APRA_CPS230 = "APRA_CPS230"  # APRA CPS 230 (Australia)
    DORA = "DORA"  # EU Digital Operational Resilience Act
    UK_OPRES = "UK_OPRES"  # UK FCA / PRA / BoE operational resilience


class ChainKind(LenientStrEnum):
    """The six dependency-chain kinds an important business service depends on."""

    PEOPLE = "people"
    PROCESS = "process"
    TECHNOLOGY = "technology"
    FACILITIES = "facilities"
    THIRD_PARTIES = "third_parties"
    DATA = "data"


class ToleranceMetric(LenientStrEnum):
    """The impact-tolerance metric kinds the tolerance engine derives."""

    MTD = "mtd"  # maximum tolerable disruption (minutes)
    RTO = "rto"  # recovery time objective (minutes)
    RPO = "rpo"  # recovery point objective (minutes)
    HARM_THRESHOLD = "harm_threshold"  # customers-affected threshold (count)


# --------------------------------------------------------------------------- #
# Resilience map (slice 3): the dependency graph for one important business service
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class ImportantBusinessService:
    """An important / critical business service the resilience map is built for."""

    id: str
    name: str
    criticality: Severity = Severity.HIGH
    tenant: str = ""


@dataclass(frozen=True, slots=True)
class DependencyNode:
    """One node in the dependency chain (a person/team, process, system, site, vendor or store)."""

    id: str
    kind: ChainKind
    name: str
    criticality: Severity = Severity.MEDIUM
    provider: str = ""
    region: str = ""
    tenant: str = ""


@dataclass(frozen=True, slots=True)
class DependencyEdge:
    """A typed, criticality-bearing edge from ``source_id`` to ``target_id``.

    The convention is "source depends on target": the important business service depends on a
    system, the system depends on a vendor, and so on, so removing a target propagates disruption
    up to every source that reaches it.
    """

    source_id: str
    target_id: str
    criticality: Severity = Severity.MEDIUM
    rationale: str = ""
    citations: tuple[Citation, ...] = ()


@dataclass(frozen=True, slots=True)
class ResilienceMap:
    """The dependency chain for one important business service (the slice-3 artifact)."""

    service: ImportantBusinessService
    nodes: tuple[DependencyNode, ...]
    edges: tuple[DependencyEdge, ...]
    citations: tuple[Citation, ...] = ()
    generated_at: object = field(default_factory=utcnow)

    @property
    def node_ids(self) -> frozenset[str]:
        return frozenset(n.id for n in self.nodes)

    @property
    def n_nodes(self) -> int:
        return len(self.nodes)

    @property
    def n_edges(self) -> int:
        return len(self.edges)

    def node(self, node_id: str) -> DependencyNode | None:
        for candidate in self.nodes:
            if candidate.id == node_id:
                return candidate
        return None


# --------------------------------------------------------------------------- #
# Ingestion + reconciliation (slice 4)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class CandidateEdge:
    """A model-proposed dependency edge, before the deterministic reconciler accepts it.

    The model proposes candidate edges with a citation; the engine accepts only schema-valid
    ones (both endpoints known), deduplicates them, and flags conflicts and unmapped
    dependencies as gaps. The model never mutates the map directly.
    """

    source_id: str
    target_id: str
    kind: ChainKind
    criticality: Severity = Severity.MEDIUM
    citation: Citation | None = None


class GapKind(LenientStrEnum):
    """Why a reconciliation or integrity gap was raised."""

    UNMAPPED_ENDPOINT = "unmapped_endpoint"  # candidate edge references an unknown node
    DUPLICATE = "duplicate"  # candidate edge duplicates an accepted one
    ORPHAN = "orphan"  # node the service cannot reach
    CYCLE = "cycle"  # a dependency cycle was broken


@dataclass(frozen=True, slots=True)
class ReconciliationGap:
    """One gap the deterministic reconciler / integrity check raised."""

    kind: GapKind
    detail: str
    ref: str = ""
    citations: tuple[Citation, ...] = ()


@dataclass(frozen=True, slots=True)
class Reconciliation:
    """The deterministic reconciliation of model-proposed edges against the known nodes."""

    accepted: tuple[DependencyEdge, ...]
    gaps: tuple[ReconciliationGap, ...]


# --------------------------------------------------------------------------- #
# Impact tolerances (slice 5)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class ImpactTolerance:
    """One derived impact-tolerance value for a service under a regulator's parameter shape."""

    service_id: str
    metric: ToleranceMetric
    value: int
    unit: str
    regulator: Regulator
    basis: str
    citations: tuple[Citation, ...] = ()


@dataclass(frozen=True, slots=True)
class ToleranceProposal:
    """A consequential impact-tolerance proposal (the slice-5 artifact).

    Setting a tolerance is consequential, so ``requires_human_review`` is unconditionally True
    and the proposal routes to Hrz7 under rule R8. The engine derives every value; the model
    drafts only the ``narrative`` justification.
    """

    service_id: str
    regulator: Regulator
    tolerances: tuple[ImpactTolerance, ...]
    narrative: str = ""
    requires_human_review: bool = True
    citations: tuple[Citation, ...] = ()


# --------------------------------------------------------------------------- #
# Scenario testing (slice 6)
# --------------------------------------------------------------------------- #


class ScenarioKind(LenientStrEnum):
    """The failure a scenario removes from the map."""

    VENDOR_FAILURE = "vendor_failure"
    SITE_LOSS = "site_loss"
    PLATFORM_OUTAGE = "platform_outage"


@dataclass(frozen=True, slots=True)
class ScenarioResult:
    """The stay-within-tolerance verdict for one removed node (the slice-6 artifact)."""

    name: str
    scenario_kind: ScenarioKind
    removed_node_id: str
    service_id: str
    computed_disruption: int  # minutes of disruption the propagation computes
    tolerance: int  # the MTD tolerance (minutes) compared against
    within_tolerance: bool
    impacted_node_ids: tuple[str, ...] = ()
    aggravators: tuple[str, ...] = ()
    citations: tuple[Citation, ...] = ()


# --------------------------------------------------------------------------- #
# The routed consequential result (rule R8 payload)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class ResilienceReview:
    """The consequential result the studio routes to Hrz7: a subject, a severity and cited reasons.

    A tolerance proposal or a breached scenario becomes one of these, carrying the severity band
    the engine computed (never a model-produced number) and the citations behind it. The review
    router and the audit sink both speak this shape.
    """

    subject: str
    severity: Severity
    decision: Decision
    summary: str
    requires_human_review: bool
    citations: tuple[Citation, ...] = ()


# --------------------------------------------------------------------------- #
# Port I/O DTOs (pure; the ports speak in terms of these)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class ExtractedDocument:
    """The structured result of extracting a source document (Doc2-shape extraction port)."""

    document_id: str
    mime_type: str
    fields: tuple[tuple[str, str], ...]
    full_text: str = ""

    def field(self, key: str) -> str:
        for name, value in self.fields:
            if name == key:
                return value
        return ""


@dataclass(frozen=True, slots=True)
class ResourceConfig:
    """A normalised technology-dependency resource (Rsk3-shape asset-inventory port)."""

    id: str
    kind: str
    name: str
    provider: str = ""
    region: str = ""
    criticality: Severity = Severity.MEDIUM
    managed: bool = True


@dataclass(frozen=True, slots=True)
class ThirdPartyArrangement:
    """One outsourcing / material arrangement read from Rgc8's register over A2A."""

    id: str
    vendor_name: str
    service: str
    criticality: Severity = Severity.MEDIUM
    region: str = ""
    material: bool = False
    tenant: str = ""


@dataclass(frozen=True, slots=True)
class ComplianceAnswer:
    """A Rsk1 Compliance Assistant answer: the outsourcing / resilience rule text + citations."""

    question: str
    answer: str
    citations: tuple[Citation, ...] = ()
    confidence: float = 0.0
    requires_human_review: bool = False


@dataclass(frozen=True, slots=True)
class GenerationRequest:
    """A narration request for the generation port (the model narrates, never decides)."""

    system_instruction: str
    prompt: str
    response_schema: dict[str, object] | None = None
    max_output_tokens: int = 1024


@dataclass(frozen=True, slots=True)
class GenerationResponse:
    """A generation-port reply: raw text plus the model id that produced it."""

    text: str
    model: str = ""
