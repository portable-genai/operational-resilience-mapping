"""ONE canonical request per port, shared by the structural and behavioural contract suites.

Parity means the same request through every implementation, so the request needs a single home.
Retyping it per suite is how two "parity" tests end up asserting different things.

Each :class:`PortCase` answers three questions about one port:

* ``invoke``   : what a single canonical call to this port looks like;
* ``answered`` : what it means for the OFFLINE family to have actually answered (a port that
  returns ``None`` and records nothing has not answered, it has merely not raised);
* ``managed_refusal`` : what the MANAGED family must do when called with no cloud reachable.
  Never a silent success: either it refuses because it is unconfigured, or its lazy SDK import
  fails. Both are honest; returning as if the work happened is not.

Adding a port means adding a case here. ``test_port_parity.py`` fails the build if this table
and the port map ever disagree, so the touch list in ``CONTRIBUTING.md`` is enforced rather than
merely written down.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from agent_eval_kit import EvalReport
from hex_service_kit.identity import IdentityError, Principal, RequestContext
from hex_service_kit.observability import TokenUsage

from operational_resilience_mapping.domain.kernel import (
    AuditEvent,
    Citation,
    Decision,
    Severity,
)
from operational_resilience_mapping.domain.models import (
    ChainKind as _ChainKind,
)
from operational_resilience_mapping.domain.models import (
    DependencyEdge,
    DependencyNode,
    GenerationRequest,
    ImportantBusinessService,
    ResilienceMap,
)

from tests.fixtures import sample_cases

#: A minimal resilience map the map-store canonical call round-trips.
CANONICAL_MAP = ResilienceMap(
    service=ImportantBusinessService(id="ibs-canonical", name="Canonical service (FICTIONAL)"),
    nodes=(DependencyNode(id="node-a", kind=_ChainKind.TECHNOLOGY, name="System A"),),
    edges=(DependencyEdge(source_id="ibs-canonical", target_id="node-a"),),
)

#: The canonical narration request the generation port answers.
CANONICAL_GENERATION = GenerationRequest(
    system_instruction="narrate", prompt="engine output", response_schema=None
)

#: The audit record every audit-port implementation is handed. Already redacted, as the port
#: requires: a raw identifier must never reach a WORM record.
CANONICAL_EVENT = AuditEvent(
    action="triage",
    actor=sample_cases.ACTOR,
    decision=Decision.ESCALATED,
    severity=Severity.HIGH,
    redacted_summary="Acme Holdings (FICTIONAL): triaged high",
    citations=(Citation(source_id="case:acme", title="Case description", snippet="urgent"),),
)

#: The escalated result every review-router implementation is handed (rule R8's payload).
CANONICAL_RESULT = sample_cases.ESCALATING_REVIEW

#: The inbound transport context every identity implementation is handed.
CANONICAL_CONTEXT = RequestContext(headers={"x-dev-persona": "auditor"})


@dataclass(frozen=True, slots=True)
class PortCase:
    """One port's canonical call plus the two verdicts the parity suites need."""

    invoke: Callable[[Any], Any]
    answered: Callable[[Any, Any], bool]
    managed_refusal: tuple[type[BaseException], ...]
    detail: str


def _audit_invoke(adapter: Any) -> Any:
    return adapter.record(CANONICAL_EVENT)


def _audit_answered(adapter: Any, _result: Any) -> bool:
    stored = adapter.log.read_all()
    return bool(stored) and stored[-1]["actor"] == sample_cases.ACTOR and adapter.verify().ok


def _identity_invoke(adapter: Any) -> Any:
    return adapter.resolve(CANONICAL_CONTEXT)


def _identity_answered(_adapter: Any, result: Any) -> bool:
    return isinstance(result, Principal) and bool(result.actor)


def _review_invoke(adapter: Any) -> Any:
    return adapter.route(CANONICAL_RESULT, maker=sample_cases.ACTOR, tenant=sample_cases.TENANT)


def _review_answered(adapter: Any, result: Any) -> bool:
    return bool(result) and len(adapter.outbox.pending()) == 1


def _map_store_invoke(adapter: Any) -> Any:
    adapter.save_map(CANONICAL_MAP, tenant=sample_cases.TENANT)
    return adapter.get_map(CANONICAL_MAP.service.id, tenant=sample_cases.TENANT)


def _map_store_answered(_adapter: Any, result: Any) -> bool:
    return isinstance(result, ResilienceMap) and result.service.id == CANONICAL_MAP.service.id


def _extraction_invoke(adapter: Any) -> Any:
    return adapter.extract("doc-settlement-runbook", b"", "application/pdf")


def _extraction_answered(_adapter: Any, result: Any) -> bool:
    return bool(getattr(result, "document_id", "")) and bool(getattr(result, "fields", ()))


def _asset_invoke(adapter: Any) -> Any:
    return adapter.scan(sample_cases.SCOPE)


def _asset_answered(_adapter: Any, result: Any) -> bool:
    return bool(result) and len(result) > 0


def _register_invoke(adapter: Any) -> Any:
    return adapter.list_arrangements(sample_cases.SCOPE)


def _register_answered(_adapter: Any, result: Any) -> bool:
    return bool(result) and len(result) > 0


def _compliance_invoke(adapter: Any) -> Any:
    return adapter.requirements("operational resilience requirements", sample_cases.ACTOR)


def _compliance_answered(_adapter: Any, result: Any) -> bool:
    return bool(getattr(result, "answer", "")) and bool(getattr(result, "citations", ()))


def _generation_invoke(adapter: Any) -> Any:
    return adapter.generate(CANONICAL_GENERATION)


def _generation_answered(_adapter: Any, result: Any) -> bool:
    return "narrative" in getattr(result, "text", "")


def _tracer_invoke(adapter: Any) -> Any:
    with adapter.span("canonical.unit", action="canonical"):
        adapter.record_token_usage(TokenUsage(input_tokens=7, output_tokens=2), "canonical-model")
    return True


def _tracer_answered(adapter: Any, result: Any) -> bool:
    return bool(result)


def _evaluation_invoke(adapter: Any) -> Any:
    return adapter.evaluate("eval/datasets/canonical.jsonl")


def _evaluation_answered(adapter: Any, result: Any) -> bool:
    return isinstance(result, EvalReport) and result.dataset.endswith("canonical.jsonl")


CANONICAL_CALLS: dict[str, PortCase] = {
    "audit": PortCase(
        invoke=_audit_invoke,
        answered=_audit_answered,
        # The lazy `google.cloud` import is the first thing the managed sink does.
        managed_refusal=(ImportError,),
        detail="write one already-redacted WORM record",
    ),
    "identity": PortCase(
        invoke=_identity_invoke,
        answered=_identity_answered,
        # No IAP assertion header offline, so the managed adapter refuses before importing.
        managed_refusal=(IdentityError,),
        detail="resolve a verified principal from transport context",
    ),
    "review_router": PortCase(
        invoke=_review_invoke,
        answered=_review_answered,
        # Rule R8: with no console configured the managed router must refuse, not swallow.
        managed_refusal=(RuntimeError,),
        detail="route one escalated result to human review",
    ),
    "map_store": PortCase(
        invoke=_map_store_invoke,
        answered=_map_store_answered,
        # The lazy AlloyDB connector import is the first thing the managed store does.
        managed_refusal=(ImportError,),
        detail="round-trip a stored resilience map",
    ),
    "extraction": PortCase(
        invoke=_extraction_invoke,
        answered=_extraction_answered,
        # The lazy Document AI import is the first thing the managed extractor does.
        managed_refusal=(ImportError,),
        detail="extract structured fields from a source document",
    ),
    "asset_inventory": PortCase(
        invoke=_asset_invoke,
        answered=_asset_answered,
        # The lazy Cloud Asset Inventory import is the first thing the managed scanner does.
        managed_refusal=(ImportError,),
        detail="return the technology dependency estate",
    ),
    "register": PortCase(
        invoke=_register_invoke,
        answered=_register_answered,
        # Rgc8 unconfigured: the managed register client refuses rather than inventing vendors.
        managed_refusal=(RuntimeError,),
        detail="list the third-party arrangements in scope",
    ),
    "compliance": PortCase(
        invoke=_compliance_invoke,
        answered=_compliance_answered,
        # Rsk1 unconfigured: the managed compliance client refuses rather than inventing text.
        managed_refusal=(RuntimeError,),
        detail="return the grounded regulatory requirement",
    ),
    "generation": PortCase(
        invoke=_generation_invoke,
        answered=_generation_answered,
        # The lazy Gemini import is the first thing the managed narrator does.
        managed_refusal=(ImportError,),
        detail="narrate the engine output",
    ),
    "tracer": PortCase(
        invoke=_tracer_invoke,
        answered=_tracer_answered,
        # NOTHING. Tracing is not essential to correctness, so the managed adapter must not refuse
        # offline either: with no SDK it degrades to a no-op and the traced body still runs. An
        # adapter that raised here would take a request down over a diagnostic.
        managed_refusal=(),
        detail="open one span and report the cost of a model call",
    ),
    "evaluation": PortCase(
        invoke=_evaluation_invoke,
        answered=_evaluation_answered,
        # The managed gate reaches Hrz4 over HTTP, which is unreachable offline.
        managed_refusal=(Exception,),
        detail="score one golden dataset through the promotion authority",
    ),
}
