"""StudioService: the resilience-studio orchestration (slices 3 to 7).

Owns the pipeline and calls only ports plus the pure engines. Every consequential number comes from
an engine (MapService integrity, ToleranceEngine, ScenarioEngine, ConcentrationService); the model
narrates only, schema-validated and discarded on failure. Consequential results (a tolerance
proposal, a breached scenario) set ``requires_human_review`` and route to human-review-console under
rule R8 in the SAME call that produced them. PII is redacted before any audit write.

The domain stays pure: this module imports no web framework and no cloud SDK. The proposer that
turns the ingested sources into candidate dependency edges is deterministic here so the offline
gate is reproducible; in a managed deployment the generation port proposes edges from the
extracted text and this same reconciler is authoritative over them.
"""

from __future__ import annotations

from pii_kit import redact

from ..ports.asset_inventory import AssetInventoryPort
from ..ports.audit import AuditSinkPort
from ..ports.compliance import CompliancePort
from ..ports.extraction import DocumentExtractionPort
from ..ports.generation import GenerationPort
from ..ports.map_store import MapStorePort
from ..ports.observability import ObservabilityTracerPort
from ..ports.register import RegisterReadPort
from ..ports.review_router import ReviewRouterPort
from .concentration_exit import (
    CloudService,
    ConcentrationFinding,
    ConcentrationService,
    PortabilityPolicy,
    ServiceCategory,
    ServicePortability,
)
from .errors import AuthorizationError
from .hitl import ResilienceReviewPolicy
from .ingestion_service import IngestionService
from .kernel import AuditEvent, Citation, Decision, Severity, utcnow
from .map_service import MapService
from .models import (
    CandidateEdge,
    ChainKind,
    ComplianceAnswer,
    DependencyNode,
    ImpactTolerance,
    ImportantBusinessService,
    Reconciliation,
    ReconciliationGap,
    Regulator,
    ResilienceMap,
    ResilienceReview,
    ResourceConfig,
    ScenarioKind,
    ScenarioResult,
    ThirdPartyArrangement,
    ToleranceMetric,
    ToleranceProposal,
)
from .narrative import build_request, numbers_are_grounded, parse_narrative
from .pii import PII_PATTERNS

_KIND_TO_CATEGORY: dict[str, ServiceCategory] = {
    "database": ServiceCategory.DB,
    "compute": ServiceCategory.COMPUTE,
    "ml": ServiceCategory.ML,
    "storage": ServiceCategory.STORAGE,
    "network": ServiceCategory.NETWORK,
    "analytics": ServiceCategory.ANALYTICS,
}

_NARRATIVE_SYSTEM = (
    "You are a documentation assistant for an operational-resilience team. Narrate the supplied "
    "engine output for a regulator-facing pack. Do not add, remove or alter any number or "
    "finding. Return JSON matching the schema."
)


#: One span per built map, and one per tolerance proposal. Sibling leaves, deliberately: the
#: tolerance surface calls the two entry points in sequence, so a pair of leaf spans times each
#: unit of work exactly once, where one wrapper span could not tell the map build from the
#: derivation. Structural attributes only: see each method's docstring.
_BUILD_MAP_SPAN = "resilience.build_map"
_PROPOSE_SPAN = "resilience.propose_tolerances"


class StudioService:
    """Build resilience maps, propose tolerances and test scenarios. Ports are explicit."""

    def __init__(
        self,
        *,
        asset_inventory: AssetInventoryPort,
        register: RegisterReadPort,
        extraction: DocumentExtractionPort,
        compliance: CompliancePort,
        generation: GenerationPort,
        map_store: MapStorePort,
        audit: AuditSinkPort,
        tracer: ObservabilityTracerPort,
        review_router: ReviewRouterPort | None = None,
    ) -> None:
        self._assets = asset_inventory
        self._register = register
        self._extraction = extraction
        self._compliance = compliance
        self._generation = generation
        self._map_store = map_store
        self._audit = audit
        # REQUIRED, and deliberately not an optional with a no-op default. A default would let a
        # new surface construct a service that emits nothing, and the deployment would look
        # traced because the exporter was bound. A surface that forgets the tracer fails to
        # construct instead, which is a failure somebody sees.
        self._tracer = tracer
        self._review_router = review_router
        self._map = MapService()
        self._ingest = IngestionService()
        self._concentration = ConcentrationService()
        self._portability = PortabilityPolicy()
        self._review_policy = ResilienceReviewPolicy()

    # ------------------------------------------------------------------ #
    # Slice 3 + 4: build and persist the resilience map
    # ------------------------------------------------------------------ #
    def build_map(
        self,
        service: ImportantBusinessService,
        scope: str,
        actor: str,
        *,
        tenant: str = "",
        document_ids: tuple[str, ...] = (),
    ) -> tuple[ResilienceMap, Reconciliation, list[ReconciliationGap]]:
        """Ingest the three sources, reconcile edges, build the map and persist it.

        The whole path runs inside one span, and its attributes are STRUCTURAL only: the
        action, the actor and the tenant. Never the service name, never the scope string,
        never a node id or a document id. A trace backend is not the WORM audit trail: it
        has no redaction stage, a wider read audience and no retention rule written against
        a regulator's requirement, so anything content-shaped that reaches a span has left
        the boundary the audit envelope exists to hold, and it has left it silently.
        """
        with self._tracer.span(_BUILD_MAP_SPAN, action="build_map", actor=actor, tenant=tenant):
            resources = list(self._assets.scan(scope))
            arrangements = list(self._register.list_arrangements(scope))
            documents = [
                self._extraction.extract(doc, b"", "application/pdf") for doc in document_ids
            ]

            tech_nodes = self._ingest.nodes_from_resources(resources)
            tp_nodes = self._ingest.nodes_from_arrangements(arrangements)
            proc_nodes = self._ingest.nodes_from_documents(documents)
            nodes = [*tech_nodes, *tp_nodes, *proc_nodes]

            candidates = self._propose_edges(service, tech_nodes, tp_nodes, proc_nodes)
            known = {service.id} | {n.id for n in nodes}
            reconciliation = self._ingest.reconcile(known, candidates)

            resilience_map, integrity_gaps = self._map.build(
                service, nodes, list(reconciliation.accepted)
            )
            self._map_store.save_map(resilience_map, tenant=tenant)
            self._audit_simple(actor, service.id, "build_map", resilience_map.n_nodes, tenant)
            return resilience_map, reconciliation, integrity_gaps

    def get_map(
        self, service_id: str, *, tenant: str = "", principal_tenant: str = ""
    ) -> ResilienceMap | None:
        """Read a stored map, authorising against the verified principal (403, never 404)."""
        stored = self._map_store.get_map(service_id, tenant=tenant)
        if stored is None:
            return None
        if principal_tenant and stored.service.tenant and stored.service.tenant != principal_tenant:
            raise AuthorizationError(
                f"principal tenant '{principal_tenant}' is not entitled to service '{service_id}'"
            )
        return stored

    # ------------------------------------------------------------------ #
    # Slice 5: propose impact tolerances (consequential, routes to human-review-console)
    # ------------------------------------------------------------------ #
    def propose_tolerances(
        self,
        service: ImportantBusinessService,
        resilience_map: ResilienceMap,
        regulator: Regulator,
        actor: str,
        *,
        tenant: str = "",
    ) -> tuple[ToleranceProposal, str]:
        """Derive tolerances, narrate the justification, and route the proposal to
        human-review-console (R8).

        The whole path runs inside one span, and its attributes are STRUCTURAL only: the
        action, the actor, the tenant and the regulator, an enum. Never the service name,
        never a tolerance value, never the narrative and never a citation snippet. See
        :meth:`build_map` for why a trace backend must never carry content.
        """
        with self._tracer.span(
            _PROPOSE_SPAN,
            action="propose_tolerances",
            actor=actor,
            tenant=tenant,
            regulator=regulator.value,
        ):
            from .tolerance_engine import ToleranceEngine

            requirement = self._requirements(actor)
            tolerances = ToleranceEngine().derive(
                service, resilience_map, regulator, citations=requirement.citations
            )
            chain_criticality = ToleranceEngine().chain_criticality(service, resilience_map)
            narrative = self._narrate_tolerances(service, tolerances, requirement)

            proposal = ToleranceProposal(
                service_id=service.id,
                regulator=regulator,
                tolerances=tuple(tolerances),
                narrative=narrative,
                requires_human_review=self._review_policy.requires_review(),
                citations=requirement.citations,
            )
            severity = self._review_policy.proposal_severity(chain_criticality)
            summary = (
                f"{service.name}: proposed {len(tolerances)} impact tolerances under "
                f"{regulator.value} (chain criticality {chain_criticality.value})"
            )
            review = ResilienceReview(
                subject=service.name,
                severity=severity,
                decision=Decision.ESCALATED,
                summary=summary,
                requires_human_review=True,
                citations=requirement.citations,
            )
            review_ref = self._audit_and_route("propose_tolerances", review, actor, tenant)
            return proposal, review_ref

    # ------------------------------------------------------------------ #
    # Slice 6: stay-within-tolerance scenario testing
    # ------------------------------------------------------------------ #
    def run_scenario(
        self,
        resilience_map: ResilienceMap,
        removed_node_id: str,
        tolerances: list[ImpactTolerance],
        actor: str,
        *,
        scope: str = "",
        scenario_kind: ScenarioKind = ScenarioKind.VENDOR_FAILURE,
        tenant: str = "",
    ) -> tuple[ScenarioResult, str]:
        """Remove a node, propagate disruption, compare to MTD, and route a breach to
        human-review-console (R8).
        """
        from .scenario_engine import ScenarioEngine

        mtd = self._mtd_minutes(tolerances)
        aggravators = self._scenario_aggravators(scope or resilience_map.service.id)
        scenario = ScenarioEngine().run(
            resilience_map,
            removed_node_id,
            mtd,
            scenario_kind=scenario_kind,
            aggravators_by_node=aggravators,
        )
        severity = self._review_policy.scenario_severity(scenario)
        decision = Decision.ESCALATED if not scenario.within_tolerance else Decision.ALLOWED
        verdict = "BREACHES" if not scenario.within_tolerance else "stays within"
        summary = (
            f"{resilience_map.service.name}: scenario '{scenario.name}' computed "
            f"{scenario.computed_disruption}m disruption which {verdict} the "
            f"{scenario.tolerance}m tolerance"
        )
        review = ResilienceReview(
            subject=resilience_map.service.name,
            severity=severity,
            decision=decision,
            summary=summary,
            requires_human_review=not scenario.within_tolerance,
            citations=scenario.citations,
        )
        review_ref = ""
        if not scenario.within_tolerance:
            review_ref = self._audit_and_route("run_scenario", review, actor, tenant)
        else:
            self._audit_simple(actor, resilience_map.service.id, "run_scenario", 1, tenant)
        return scenario, review_ref

    # ------------------------------------------------------------------ #
    # Concentration (`domain/concentration_exit/`) used to ground scenario aggravators
    # ------------------------------------------------------------------ #
    def concentration(self, scope: str) -> list[ConcentrationFinding]:
        """Deterministic concentration findings over the scope's cloud services + third parties."""
        services = self._cloud_services(scope)
        portability = [self._assess(s) for s in services]
        raw = self._concentration.detect(services, portability)
        requirement = self._requirements("system")
        return [self._ground(f, requirement.citations) for f in raw]

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _cloud_services(self, scope: str) -> list[CloudService]:
        services: list[CloudService] = []
        for resource in self._assets.scan(scope):
            services.append(self._resource_to_cloud(resource))
        for arrangement in self._register.list_arrangements(scope):
            services.append(self._arrangement_to_cloud(arrangement))
        return services

    @staticmethod
    def _resource_to_cloud(resource: ResourceConfig) -> CloudService:
        return CloudService(
            id=resource.id,
            name=resource.name,
            category=_KIND_TO_CATEGORY.get(resource.kind, ServiceCategory.OTHER),
            criticality=resource.criticality,
            region=resource.region or None,
            provider=resource.provider or "gcp",
            managed=resource.managed,
        )

    @staticmethod
    def _arrangement_to_cloud(arrangement: ThirdPartyArrangement) -> CloudService:
        return CloudService(
            id=arrangement.id,
            name=arrangement.vendor_name,
            category=ServiceCategory.OTHER,
            criticality=arrangement.criticality,
            region=arrangement.region or None,
            provider=arrangement.vendor_name,
            managed=True,
            tenant=arrangement.tenant,
        )

    def _assess(self, service: CloudService) -> ServicePortability:
        base = self._portability.baseline_for(service)
        return ServicePortability(
            service=service,
            rating=base.rating,
            portable_target=base.portable_target,
            open_standard=base.open_standard,
            effort=base.effort,
        )

    def _scenario_aggravators(self, scope: str) -> dict[str, tuple[str, ...]]:
        """LOCKED critical services have no exit path, so their failure aggravates a scenario."""
        out: dict[str, tuple[str, ...]] = {}
        for service in self._cloud_services(scope):
            assessment = self._assess(service)
            if assessment.is_locked and service.criticality in (Severity.HIGH, Severity.CRITICAL):
                out[service.id] = (
                    f"{service.name} is a LOCKED critical service with no open-standard exit "
                    "path, so its failure has no rehearsed recovery route",
                )
        return out

    @staticmethod
    def _ground(
        finding: ConcentrationFinding, citations: tuple[Citation, ...]
    ) -> ConcentrationFinding:
        if not citations:
            return finding
        return ConcentrationFinding(
            dimension=finding.dimension,
            level=finding.level,
            detail=finding.detail,
            regulatory_ref=finding.regulatory_ref,
            remediation=finding.remediation,
            citations=citations,
        )

    def _requirements(self, actor: str) -> ComplianceAnswer:
        try:
            answer = self._compliance.requirements("operational resilience requirements", actor)
        except Exception:  # noqa: BLE001 - compliance unavailable must not crash the pipeline
            return ComplianceAnswer(
                question="operational resilience requirements",
                answer="compliance source unavailable; deterministic basis stands, review first",
                citations=(),
                requires_human_review=True,
            )
        return answer

    def _narrate_tolerances(
        self,
        service: ImportantBusinessService,
        tolerances: list[ImpactTolerance],
        requirement: ComplianceAnswer,
    ) -> str:
        """Draft the tolerance justification. The prompt is REDACTED before it leaves.

        ``service.name`` is client-supplied: it arrives verbatim in the ``POST /v1/tolerance``
        body and is never validated as a label. ``requirement.answer`` is regulatory prose from
        the compliance port, which the managed adapter reads from compliance-advisory over the wire.
        Both
        reached the bound generation adapter unmasked, so under the ``gcp`` profile a raw
        identifier in a service name was sent to Gemini, while the audit write two frames later
        was careful to mask the same string. The model boundary is a separate sink from the WORM
        record and needs its own redaction, not the audit's.

        Only the prompt is masked. The tolerance figures are the engine's and are never touched:
        redaction must not be able to change a number.
        """
        allowed = {t.value for t in tolerances}
        deterministic = "; ".join(
            f"{t.metric.value.upper()} {t.value} {t.unit}" for t in tolerances
        )
        prompt = redact(
            f"Service: {service.name}. Regulatory basis: {requirement.answer}. "
            f"Engine-derived tolerances: {deterministic}.",
            PII_PATTERNS,
        )
        try:
            response = self._generation.generate(build_request(_NARRATIVE_SYSTEM, prompt))
        except Exception:  # noqa: BLE001 - narration must never fail the proposal
            return f"Proposed tolerances: {deterministic}."
        narrative = parse_narrative(response)
        if not narrative or not numbers_are_grounded(narrative, allowed):
            # Discard an unusable or ungrounded narrative; the deterministic prose stands.
            return f"Proposed tolerances: {deterministic}."
        return narrative

    @staticmethod
    def _mtd_minutes(tolerances: list[ImpactTolerance]) -> int:
        for tolerance in tolerances:
            if tolerance.metric is ToleranceMetric.MTD:
                return tolerance.value
        return 0

    def _propose_edges(
        self,
        service: ImportantBusinessService,
        tech_nodes: list[DependencyNode],
        tp_nodes: list[DependencyNode],
        proc_nodes: list[DependencyNode],
    ) -> list[CandidateEdge]:
        """Deterministic candidate dependency edges from the ingested structure.

        Stands in for the model's edge proposals offline. Each edge carries a citation to the
        source it came from; the reconciler is authoritative over these candidates.
        """
        cite = Citation(source_id="ingestion", title="Ingested dependency structure")
        edges: list[CandidateEdge] = []
        tech_ids = {n.id for n in tech_nodes}
        tp_ids = {n.id for n in tp_nodes}

        for node in tech_nodes:
            edges.append(
                CandidateEdge(service.id, node.id, ChainKind.TECHNOLOGY, node.criticality, cite)
            )
        for proc in proc_nodes:
            edges.append(
                CandidateEdge(service.id, proc.id, ChainKind.PROCESS, proc.criticality, cite)
            )
        # System-to-third-party dependencies (the fictional estate's known wiring).
        wiring = {
            "svc-payments-api": "tp-card-network",
            "svc-ledger-db": "tp-cloud-provider",
            "svc-object-store": "tp-cloud-provider",
            "svc-fraud-scorer": "tp-kyc-bureau",
        }
        for src, dst in wiring.items():
            if src in tech_ids and dst in tp_ids:
                edges.append(CandidateEdge(src, dst, ChainKind.THIRD_PARTIES, Severity.HIGH, cite))
        return edges

    # ------------------------------------------------------------------ #
    # Audit + review routing (rule R8)
    # ------------------------------------------------------------------ #
    def _audit_and_route(
        self, action: str, review: ResilienceReview, actor: str, tenant: str
    ) -> str:
        self._record(
            AuditEvent(
                action=action,
                actor=actor,
                decision=review.decision,
                severity=review.severity,
                redacted_summary=redact(review.summary, PII_PATTERNS),
                citations=review.citations,
                timestamp=utcnow(),
            )
        )
        if self._review_router is not None and review.requires_human_review:
            return self._review_router.route(review, maker=actor, tenant=tenant)
        return ""

    def _audit_simple(self, actor: str, target: str, action: str, count: int, tenant: str) -> None:
        _ = tenant
        self._record(
            AuditEvent(
                action=action,
                actor=actor,
                decision=Decision.ALLOWED,
                severity=Severity.LOW,
                redacted_summary=redact(f"{action}:{target}:{count}", PII_PATTERNS),
                citations=(),
                timestamp=utcnow(),
            )
        )

    def _record(self, event: AuditEvent) -> None:
        # The WORM audit write is consequential and is NOT swallowed: a chain error (e.g. a
        # truncated tail detected on the next append) must surface, not be lost, so the record
        # of what happened is never quietly skipped.
        self._audit.record(event)
