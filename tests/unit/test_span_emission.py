"""The studio's two entry points open ONE leaf span each, and no span carries content.

A trace backend is not the WORM audit trail. It has no redaction stage, no retention policy
written against a regulator's requirement, and a far wider read audience than the audit store.
So the value of tracing these paths depends entirely on the spans carrying structural
attributes only: which action, whose, which tenant, which regulator. A service name, the scope
string, a node id, a tolerance value or a planted identifier reaching a span has left the
boundary redaction exists to hold, and it has left it silently.

The two spans are SIBLINGS, deliberately: the tolerance surface calls ``build_map`` and then
``propose_tolerances`` in sequence, so a pair of leaf spans times each unit of work exactly
once, where a wrapper could not tell the map build from the derivation. The content case
drives a service whose name carries a planted NRIC, so the check runs against input that
would actually leak if any attribute were content-shaped.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from operational_resilience_mapping.config import Container, build_container
from operational_resilience_mapping.domain.kernel import Severity
from operational_resilience_mapping.domain.models import (
    ImportantBusinessService,
    Regulator,
    ToleranceProposal,
)
from operational_resilience_mapping.domain.studio_service import StudioService

from tests.conftest import local_settings
from tests.fixtures import sample_cases

#: The complete attribute key set each span may carry. Adding to one of these is a decision
#: about what leaves the trust boundary, so it is made here rather than at the call site.
_BUILD_MAP_KEYS = {"action", "actor", "tenant"}
_PROPOSE_KEYS = {"action", "actor", "tenant", "regulator"}

#: A service whose name carries the planted identifier, so a span that leaked the service
#: name would fail on this literal rather than on a subtlety.
_PII_SERVICE = ImportantBusinessService(
    id="ibs-pii-payments",
    name=f"Payments owner NRIC {sample_cases.PLANTED_NRIC} (FICTIONAL)",
    criticality=Severity.CRITICAL,
)


class _RecordingTracer:
    """Captures every span name, attribute and nesting depth so the test can inspect them."""

    def __init__(self) -> None:
        self.spans: list[tuple[str, dict[str, str]]] = []
        self.depths: list[int] = []
        self._open = 0

    @contextmanager
    def span(self, name: str, **attributes: str) -> Iterator[None]:
        self.spans.append((name, dict(attributes)))
        self.depths.append(self._open)
        self._open += 1
        try:
            yield
        finally:
            self._open -= 1

    def record_token_usage(self, usage: object, model: str) -> None:
        return None


def _studio(container: Container, tracer: _RecordingTracer) -> StudioService:
    """The REAL local adapters, exactly as ``factory.build_studio`` wires them."""
    return StudioService(
        asset_inventory=container.asset_inventory,
        register=container.register,
        extraction=container.extraction,
        compliance=container.compliance,
        generation=container.generation,
        map_store=container.map_store,
        audit=container.audit,
        tracer=tracer,  # type: ignore[arg-type]
        review_router=container.review_router,
    )


def _drive(
    service: ImportantBusinessService,
) -> tuple[_RecordingTracer, ToleranceProposal]:
    """The whole tolerance journey: build the map, then propose, as the API route does."""
    container = build_container(local_settings())
    tracer = _RecordingTracer()
    studio = _studio(container, tracer)
    resilience_map, _reconciliation, _gaps = studio.build_map(
        service, sample_cases.SCOPE, actor=sample_cases.ACTOR, tenant=sample_cases.TENANT
    )
    proposal, _ref = studio.propose_tolerances(
        service,
        resilience_map,
        Regulator.APRA_CPS230,
        actor=sample_cases.ACTOR,
        tenant=sample_cases.TENANT,
    )
    return tracer, proposal


def _emitted(tracer: _RecordingTracer) -> str:
    """Every attribute KEY and VALUE that was emitted, as one searchable blob."""
    parts: list[str] = []
    for name, attributes in tracer.spans:
        parts.append(name)
        parts.extend(attributes)
        parts.extend(attributes.values())
    return " ".join(parts)


def test_the_tolerance_journey_opens_two_sibling_leaf_spans() -> None:
    """One per unit of work, neither wrapping the other, so nothing is timed twice."""
    tracer, _ = _drive(sample_cases.SERVICE)
    assert [name for name, _ in tracer.spans] == [
        "resilience.build_map",
        "resilience.propose_tolerances",
    ]
    assert tracer.depths == [0, 0], "the two spans are siblings, not parent and child"


def test_the_build_map_span_carries_the_structural_attributes_an_operator_needs() -> None:
    tracer, _ = _drive(sample_cases.SERVICE)
    _, attributes = tracer.spans[0]
    assert attributes["action"] == "build_map"
    assert attributes["actor"] == sample_cases.ACTOR
    assert attributes["tenant"] == sample_cases.TENANT


def test_the_propose_span_carries_the_structural_attributes_an_operator_needs() -> None:
    """Enough to answer "whose proposal is slow, under which regime", and nothing more."""
    tracer, _ = _drive(sample_cases.SERVICE)
    _, attributes = tracer.spans[1]
    assert attributes["action"] == "propose_tolerances"
    assert attributes["actor"] == sample_cases.ACTOR
    assert attributes["tenant"] == sample_cases.TENANT
    assert attributes["regulator"] == Regulator.APRA_CPS230.value


def test_the_attribute_sets_are_a_fixed_allowlist_even_when_the_proposal_escalates() -> None:
    """The proposal always escalates (R8), and must not explain itself on the span."""
    tracer, proposal = _drive(sample_cases.SERVICE)
    assert proposal.requires_human_review, (
        "tolerance proposals stopped escalating, so this test no longer proves an "
        "escalating result keeps its content off the span"
    )
    assert set(tracer.spans[0][1]) == _BUILD_MAP_KEYS
    assert set(tracer.spans[1][1]) == _PROPOSE_KEYS, (
        "a new span attribute appeared; confirm it is structural, then widen "
        "_PROPOSE_KEYS here deliberately"
    )


def test_no_span_attribute_carries_service_content_or_the_planted_identifier() -> None:
    """The service used here has an NRIC planted in its name, so a leak would show."""
    tracer, proposal = _drive(_PII_SERVICE)
    emitted = _emitted(tracer)

    forbidden = [
        sample_cases.PLANTED_NRIC,
        _PII_SERVICE.id,
        _PII_SERVICE.name,
        sample_cases.SCOPE,
        proposal.narrative,
    ]
    for literal in forbidden:
        if not literal:
            continue
        assert literal.lower() not in emitted.lower(), f"a span attribute carried {literal!r}"
    assert sample_cases.PLANTED_NRIC not in emitted


def test_every_emitted_attribute_value_is_a_string_the_port_declares() -> None:
    """``span(name, **attributes: str)``: a non-string would serialise however the SDK felt."""
    tracer, _ = _drive(sample_cases.SERVICE)
    values: list[Any] = [v for _, attributes in tracer.spans for v in attributes.values()]
    assert values
    assert all(isinstance(value, str) for value in values)
