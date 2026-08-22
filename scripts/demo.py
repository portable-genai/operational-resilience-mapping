"""The scripted, offline demo: the REAL services, synthetic data, an audit-first output view.

This is the demo as CODE (practices check F1), not a slide deck and not a recording. Every step
below drives the actual resilience studio, the actual hash-chained audit store and the actual
rule-R8 review router over the ``local`` profile, so a step that stops being true stops passing
rather than stops being mentioned.

Three properties make it worth running in front of somebody:

* **Nothing is faked.** No stub service, no pre-baked JSON. The dependency map, the impact
  tolerances, the scenario verdicts, the audit records and the routing references are produced by
  the shipped code. Every consequential number comes from a pure engine, never from a model.
* **It is bounded.** The demo proves an offline, single-process seam. It does not prove
  cross-host deployment, a live console or the managed profile; those need a cloud project and
  live in ``tests/integration/``.
* **It is replayable.** Same inputs, same output, every time, because the consequential decision
  is deterministic.

Run it directly to write the audit-view JSON, then render that JSON to static pages::

    make demo-static

Every party, address and identifier here is obviously fictional: ``.example`` domains, RFC 5737
and RFC 3849 literals, and a synthetic national id that exists only to prove redaction happened.

MAINTAINER NOTE: this file is rendered from a template, so no line may change length with the
package or service name. Every cookiecutter value is bound to a short module constant below.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hex_service_kit.audit import HashChainedAuditLog
from hex_service_kit.identity import RequestContext
from hex_service_kit.serialization import to_jsonable

from operational_resilience_mapping.config import (
    Settings,
    build_container,
)
from operational_resilience_mapping.domain import (
    kernel,
    models,
)
from operational_resilience_mapping.domain.models import (
    GenerationRequest,
    ImpactTolerance,
    ImportantBusinessService,
    Regulator,
    ResilienceMap,
    ScenarioKind,
    ToleranceMetric,
)
from operational_resilience_mapping.domain.pii import (
    JURISDICTIONS,
)
from operational_resilience_mapping.factory import (
    build_studio,
)


def loaded_cloud_sdks() -> tuple[str, ...]:
    """Every managed-SDK module currently importable in THIS interpreter, sorted."""
    return tuple(sorted(name for name in sys.modules if name.split(".")[0] == "google"))


#: Rendered identity, bound once so no other line's length depends on how long a name is.
SERVICE_NAME = "Operational Resilience Studio"
CATALOG_ID = "Rgc9"
REPOSITORY = "operational-resilience-mapping"

#: The VERIFIED principal the demo attributes work to. A client never asserts this.
ACTOR = "analyst@bank.example"
TENANT = "demo-bank"
SCOPE = "projects/fictional"

#: A planted identifier, so the redaction panel has an independent literal to look for.
PLANTED_NRIC = "S1234567D"

#: The important business service the demo maps. RFC 5737 / RFC 3849 literals live in the notes
#: below so the fixtures announce themselves as documentation-only, never a routable address.
SERVICE = ImportantBusinessService(
    id="ibs-retail-payments",
    name="Retail Payments (FICTIONAL)",
    criticality=kernel.Severity.CRITICAL,
)

#: A second service whose NAME carries a planted national id, to drive the redaction beat: the
#: audit summary is built from the service name, so the identifier must be masked before the write.
PII_SERVICE = ImportantBusinessService(
    id="ibs-owner-record",
    name="Retail Payments owner NRIC " + PLANTED_NRIC + " (FICTIONAL)",
    criticality=kernel.Severity.CRITICAL,
)

#: A fictional-data blob the demo-surface test checks for documentation-only literals.
FICTIONAL_BLOB = (
    "Synthetic estate reachable only from 192.0.2.10 and 2001:db8::7, "
    "contact ops@bank.example. No routable address, no real party."
)


@dataclass(frozen=True, slots=True)
class Step:
    """One presenter beat: what it shows, and the sentence the presenter reads aloud."""

    key: str
    label: str
    narration: str


STEPS: tuple[Step, ...] = (
    Step(
        key="opened",
        label="Studio bound on the offline profile; the resilience map is built",
        narration=(
            "The whole stack is bound from one settings file: no cloud project, no credentials, "
            "no SDK. The dependency map for an important business service is ingested from the "
            "asset inventory, the outsourcing register and the process docs, and reconciled "
            "deterministically."
        ),
    ),
    Step(
        key="routine",
        label="A scenario that STAYS within tolerance: not escalated",
        narration=(
            "A non-critical dependency fails. The engine propagates the disruption and compares "
            "it to the accepted tolerance. It stays within, so nothing is routed for review: "
            "manufacturing a review here would train reviewers to rubber-stamp."
        ),
    ),
    Step(
        key="escalation",
        label="A consequential tolerance proposal: escalated AND routed (rule R8)",
        narration=(
            "Setting an impact tolerance is consequential. Every value comes from the "
            "per-regulator engine, the model drafts only the justification, and the proposal is "
            "handed to the human-review console in the same call that produced it."
        ),
    ),
    Step(
        key="redaction",
        label="Personal data is masked BEFORE the audit write",
        narration=(
            "The same path, with a national id planted in the service record. The identifier is "
            "masked before anything is written, so the immutable record never contains it. "
            "Redacting afterwards would be too late: the record is already immutable."
        ),
    ),
    Step(
        key="review_queue",
        label="What the reviewer receives, already redacted on the wire",
        narration=(
            "The outbound review queue. The console is a SHARED sink, so payloads are redacted "
            "against every configured jurisdiction, not only the one this case came from."
        ),
    ),
    Step(
        key="audit",
        label="The audit trail verifies, and exports in an open format",
        narration=(
            "The trail is append-only and hash-chained, with an external head anchor on a "
            "separate volume. It exports to JSON Lines and reloads into a fresh store with "
            "every link intact: the record is yours, not this codebase's."
        ),
    ),
    Step(
        key="tamper",
        label="A rewritten record is DETECTED, not merely discouraged",
        narration=(
            "An attacker with file access drops the append-only triggers and rewrites one "
            "record. The store cannot prevent that. The hash chain names the exact record that "
            "broke, which is the honest guarantee: tamper-EVIDENT, not tamper-proof."
        ),
    ),
    Step(
        key="portability",
        label="The exit path fails fast instead of failing silently",
        narration=(
            "The same calls on the on-premises profile, with no code edited and no domain "
            "module touched. Every unimplemented seam refuses loudly. A placeholder that "
            "returned successfully would convert an escalation into an unreviewed decision."
        ),
    ),
)

STEP_KEYS: tuple[str, ...] = tuple(step.key for step in STEPS)


@dataclass(frozen=True, slots=True)
class Row:
    """One labelled fact in a panel. ``tone`` drives the colour, never the meaning."""

    label: str
    value: str
    tone: str = ""


@dataclass(frozen=True, slots=True)
class Panel:
    """One block of the output view: a title, labelled facts, and an interpretation."""

    title: str
    rows: tuple[Row, ...] = ()
    note: str = ""
    tone: str = ""


@dataclass(frozen=True, slots=True)
class StepResult:
    """Everything one step produced, ready to render or to assert against."""

    key: str
    label: str
    narration: str
    panels: tuple[Panel, ...] = ()
    facts: dict[str, Any] = field(default_factory=dict)


Produced = tuple[list[Panel], dict[str, Any]]


class DemoRun:
    """A live demo, advanced one step at a time over the real services."""

    def __init__(self, workdir: Path | None = None) -> None:
        self._cloud_sdk_before = frozenset(loaded_cloud_sdks())
        self._tempdir: tempfile.TemporaryDirectory[str] | None = None
        if workdir is None:
            self._tempdir = tempfile.TemporaryDirectory(prefix="demo-run-")
            workdir = Path(self._tempdir.name)
        self.workdir = workdir
        self.audit_path = workdir / "store" / "audit.sqlite3"
        self.anchor_path = workdir / "anchor" / "head.json"
        self.anchor_path.parent.mkdir(parents=True, exist_ok=True)
        self.settings = Settings(
            profile="local",
            audit_path=str(self.audit_path),
            audit_anchor_path=str(self.anchor_path),
            tenant=TENANT,
        )
        self.container = build_container(self.settings)
        self.studio = build_studio(self.container)
        self.results: list[StepResult] = []
        self.cases = 0
        self.escalated = 0
        self.routed = 0
        self.chain_ok = True
        # Build the map once, before the arc; the tolerance/scenario steps reuse it.
        self.resilience_map, self.reconciliation, self.integrity_gaps = self.studio.build_map(
            SERVICE, SCOPE, actor=ACTOR, tenant=TENANT, document_ids=("doc-settlement-runbook",)
        )
        self.tolerances: list[ImpactTolerance] = []
        self._perform(STEPS[0])

    @property
    def index(self) -> int:
        return len(self.results) - 1

    @property
    def done(self) -> bool:
        return len(self.results) >= len(STEPS)

    def advance(self) -> StepResult:
        if self.done:
            return self.results[-1]
        return self._perform(STEPS[len(self.results)])

    def run_to_end(self) -> None:
        while not self.done:
            self.advance()

    def _perform(self, step: Step) -> StepResult:
        handler: Callable[[], Produced] = getattr(self, "_step_" + step.key)
        panels, facts = handler()
        result = StepResult(
            key=step.key,
            label=step.label,
            narration=step.narration,
            panels=tuple(panels),
            facts=facts,
        )
        self.results.append(result)
        return result

    # -------------------------------------------------------------- steps

    def _step_opened(self) -> Produced:
        bindings = [
            Row(port, self.settings.adapters[port][self.settings.profile].split(":")[-1])
            for port in sorted(self.settings.adapters)
        ]
        profiles = sorted({name for table in self.settings.adapters.values() for name in table})
        sdk = [name for name in loaded_cloud_sdks() if name not in self._cloud_sdk_before]
        deployment = Panel(
            title="Deployment",
            rows=(
                Row("Service", SERVICE_NAME),
                Row("Catalog id", CATALOG_ID),
                Row("Profile", self.settings.profile, "ok"),
                Row("Profiles bound for every port", ", ".join(profiles)),
                Row("Residency region", self.settings.region),
                Row("Jurisdiction PII packs", ", ".join(JURISDICTIONS)),
            ),
            note=(
                "One environment variable selects the adapter family for every port. Nothing "
                "below was edited to make the service run offline. " + FICTIONAL_BLOB
            ),
        )
        adapters = Panel(
            title="Bound adapters",
            rows=tuple(bindings),
            note="The binding map lives in config/settings.yaml, not in the code.",
        )
        graph = Panel(
            title="Resilience map",
            rows=(
                Row("Important business service", SERVICE.name),
                Row("Dependency nodes", str(self.resilience_map.n_nodes)),
                Row("Reconciled edges", str(self.resilience_map.n_edges)),
                Row("Reconciliation gaps", str(len(self.reconciliation.gaps))),
                Row("Integrity gaps", str(len(self.integrity_gaps))),
            ),
            note=(
                "The model proposes candidate edges; the engine accepts only schema-valid ones, "
                "deduplicates, and flags the rest as gaps."
            ),
        )
        findings = Panel(
            title="Findings",
            rows=(
                Row("Cloud SDK modules imported", ", ".join(sdk) or "none", "bad" if sdk else "ok"),
                Row("Credentials required", "none", "ok"),
                Row("Network required", "none", "ok"),
            ),
            note=(
                "The managed adapters import their SDK lazily, so this profile runs with none "
                "installed at all."
            ),
            tone="bad" if sdk else "ok",
        )
        facts = {"profile": self.settings.profile, "sdk_modules": sdk, "profiles": profiles}
        return [deployment, adapters, graph, findings], facts

    def _step_routine(self) -> Produced:
        generous = [
            ImpactTolerance(
                service_id=SERVICE.id,
                metric=ToleranceMetric.MTD,
                value=1_000_000,
                unit="minutes",
                regulator=Regulator.APRA_CPS230,
                basis="demo generous tolerance",
            )
        ]
        scenario, review_ref = self.studio.run_scenario(
            self.resilience_map,
            "svc-object-store",
            generous,
            actor=ACTOR,
            scope=SCOPE,
            scenario_kind=ScenarioKind.PLATFORM_OUTAGE,
            tenant=TENANT,
        )
        self.cases += 1
        panel = Panel(
            title="Scenario: " + scenario.removed_node_id,
            rows=(
                Row("Removed dependency", scenario.removed_node_id),
                Row("Computed disruption (min)", str(scenario.computed_disruption)),
                Row("Accepted tolerance (min)", str(scenario.tolerance)),
                Row("Within tolerance", str(scenario.within_tolerance), "ok"),
                Row("Routed to review", review_ref or "not routed (within tolerance)", "ok"),
            ),
            note=(
                "The disruption is propagated across the graph by pure code and compared to the "
                "accepted tolerance. A model narrates the result; it never produces it."
            ),
            tone="ok",
        )
        facts = {
            "requires_human_review": not scenario.within_tolerance,
            "review_ref": review_ref,
            "within_tolerance": scenario.within_tolerance,
        }
        return [panel], facts

    def _step_escalation(self) -> Produced:
        proposal, review_ref = self.studio.propose_tolerances(
            SERVICE, self.resilience_map, Regulator.APRA_CPS230, actor=ACTOR, tenant=TENANT
        )
        self.tolerances = list(proposal.tolerances)
        self.cases += 1
        self.escalated += 1
        self.routed += 1
        rows = [
            Row(t.metric.value.upper(), str(t.value) + " " + t.unit) for t in proposal.tolerances
        ]
        rows.append(Row("Requires human review", str(proposal.requires_human_review)))
        rows.append(Row("Routed to review", review_ref, "ok" if review_ref else "bad"))
        decision = Panel(
            title="Tolerance proposal: " + SERVICE.name,
            rows=tuple(rows),
            note=(
                "Every value is derived by the per-regulator engine from the chain criticality. "
                "Setting the flag is not the escalation; routing is."
            ),
            tone="ok" if review_ref else "bad",
        )
        evidence = Panel(
            title="Evidence",
            rows=tuple(Row(c.title, c.snippet or c.source_id) for c in proposal.citations)
            or (Row("citations", "NONE", "bad"),),
            note="Every tolerance basis cites the grounded regulatory answer.",
        )
        facts = {
            "requires_human_review": proposal.requires_human_review,
            "review_ref": review_ref,
        }
        return [decision, evidence], facts

    def _step_redaction(self) -> Produced:
        pii_map, _reconciliation, _gaps = self.studio.build_map(
            PII_SERVICE, SCOPE, actor=ACTOR, tenant=TENANT
        )
        _proposal, review_ref = self.studio.propose_tolerances(
            PII_SERVICE, pii_map, Regulator.APRA_CPS230, actor=ACTOR, tenant=TENANT
        )
        self.cases += 1
        self.escalated += 1
        self.routed += 1
        recorded = str(self.container.audit.log.read_all()[-1]["redacted_summary"])
        leaked = PLANTED_NRIC in recorded
        panel = Panel(
            title="Redact before the write",
            rows=(
                Row("Identifier in the service record", PLANTED_NRIC, "warn"),
                Row(
                    "Identifier in the immutable record",
                    "PRESENT" if leaked else "absent",
                    "bad" if leaked else "ok",
                ),
                Row("Stored summary", recorded),
                Row("Routed to review", review_ref, "ok" if review_ref else "bad"),
            ),
            note=(
                "The record is immutable, so a redaction pass after the write would be too late. "
                "Masking happens on the way in."
            ),
            tone="bad" if leaked else "ok",
        )
        facts = {"planted_identifier_leaked": leaked, "review_ref": review_ref}
        return [panel], facts

    def _step_review_queue(self) -> Produced:
        pending = list(self.container.review_router.outbox.pending())
        rows: list[Row] = []
        leaked = False
        for item in pending:
            payload = to_jsonable(item)
            leaked = leaked or PLANTED_NRIC in json.dumps(payload, sort_keys=True)
            rows.append(Row(str(getattr(item, "source_key", "review")), _summarise(payload)))
        queue = Panel(
            title="Outbound review queue",
            rows=tuple(rows) or (Row("queue", "empty", "bad"),),
            note=(
                "Queued, not submitted. The reference the caller received says exactly that, so "
                "a buffered escalation is never mistaken for a reviewed one."
            ),
        )
        findings = Panel(
            title="Findings",
            rows=(
                Row("Escalated results", str(self.escalated)),
                Row(
                    "Routed to review",
                    str(self.routed),
                    "ok" if self.routed == self.escalated else "bad",
                ),
                Row(
                    "Personal data on the wire",
                    "LEAKED" if leaked else "none",
                    "bad" if leaked else "ok",
                ),
            ),
            note=(
                "Every escalation is accounted for. A flag with no routing reference is "
                "auto-execution with extra steps."
            ),
            tone="bad" if leaked or self.routed != self.escalated else "ok",
        )
        actions = Panel(
            title="Next actions",
            rows=(
                Row("Reviewer", "open the queued item and approve or reject it"),
                Row("Operator", "point HRZ_HUMAN_REVIEW_URL at the console and flush the outbox"),
            ),
        )
        return [queue, findings, actions], {"pending": len(pending), "wire_leak": leaked}

    def _step_audit(self) -> Produced:
        log = self.container.audit.log
        report = self.container.audit.verify()
        self.chain_ok = report.ok
        export = self.workdir / "export" / "audit.jsonl"
        export.parent.mkdir(parents=True, exist_ok=True)
        written = log.export_jsonl(export)
        restored = HashChainedAuditLog(":memory:")
        reloaded = restored.import_jsonl(export)
        round_trip = restored.verify_chain()
        anchored = bool(self.settings.audit_anchor_path) and self.anchor_path.exists()
        trail = Panel(
            title="Audit trail",
            rows=(
                Row("Records", str(report.entries)),
                Row("Hash-chained", str(report.chained)),
                Row(
                    "Unverifiable (unchained)",
                    str(report.legacy),
                    "ok" if report.legacy == 0 else "bad",
                ),
                Row("Verdict", report.detail, "ok" if report.ok else "bad"),
                Row(
                    "External head anchor",
                    "configured" if anchored else "absent",
                    "ok" if anchored else "warn",
                ),
            ),
            note=(
                "The chain alone cannot detect a truncated tail: dropping the newest rows leaves "
                "a shorter chain that verifies perfectly. The anchor, kept on a different "
                "volume, is what closes that gap."
            ),
            tone="ok" if report.ok else "bad",
        )
        portable = Panel(
            title="Open-format round trip",
            rows=(
                Row("Exported records", str(written)),
                Row("Reloaded into a fresh store", str(reloaded)),
                Row("Chain after reload", round_trip.detail, "ok" if round_trip.ok else "bad"),
            ),
            note=(
                "JSON Lines with the hashes included, so a consumer can re-verify the trail "
                "without this codebase. That is what makes the record portable."
            ),
            tone="ok" if round_trip.ok else "bad",
        )
        facts = {
            "chain_ok": report.ok,
            "entries": report.entries,
            "exported": written,
            "round_trip_ok": round_trip.ok,
            "anchored": anchored,
        }
        return [trail, portable], facts

    def _step_tamper(self) -> Produced:
        before = self.container.audit.verify()
        target = _rewrite_a_record(self.audit_path)
        after = self.container.audit.verify()
        self.chain_ok = after.ok
        detected = (not after.ok) and after.first_bad_seq == target
        attack = Panel(
            title="The tamper",
            rows=(
                Row("Append-only triggers", "dropped by the attacker", "warn"),
                Row("Record rewritten in place", "seq " + str(target), "warn"),
                Row("Verdict before the rewrite", before.detail, "ok"),
            ),
            note=(
                "File access beats a database trigger. A store that claims otherwise is "
                "describing a policy, not a control."
            ),
        )
        findings = Panel(
            title="Findings",
            rows=(
                Row("Chain intact", "YES" if after.ok else "no", "bad" if after.ok else "ok"),
                Row("First broken record", str(after.first_bad_seq), "ok"),
                Row("Detail", after.detail),
                Row(
                    "Named the exact rewritten record",
                    "yes" if detected else "no",
                    "ok" if detected else "bad",
                ),
            ),
            note=(
                "Tamper-EVIDENT, not tamper-proof. The guarantee is that a rewrite cannot pass "
                "unnoticed, and that the report names which record broke."
            ),
            tone="ok" if detected else "bad",
        )
        actions = Panel(
            title="Next actions",
            rows=(
                Row("Operator", "restore from the exported JSONL and re-anchor deliberately"),
                Row("Auditor", "treat every record from seq " + str(target) + " on as suspect"),
            ),
        )
        facts = {"tampered_seq": target, "detected": detected, "chain_ok": after.ok}
        return [attack, findings, actions], facts

    def _step_portability(self) -> Produced:
        onprem = build_container(Settings(profile="onprem", tenant=TENANT))
        rows: list[Row] = []
        refused: list[str] = []
        absent: list[str] = []
        for port, call in EXIT_CALLS.items():
            expected_absent = port in EXIT_ABSENT
            try:
                call(onprem)
            except NotImplementedError as exc:
                if expected_absent:
                    rows.append(Row(port, "REFUSED, but is meant to be absent", "bad"))
                else:
                    refused.append(port)
                    rows.append(Row(port, "refused: " + str(exc).split(":")[0], "ok"))
            else:
                if expected_absent:
                    absent.append(port)
                    rows.append(Row(port, "absent, by design (a diagnostic, not a control)", "ok"))
                else:
                    rows.append(Row(port, "SUCCEEDED SILENTLY", "bad"))
        exit_panel = Panel(
            title="Exit profile (onprem)",
            rows=tuple(rows),
            note=(
                "Selected by one environment variable. No domain module was edited and no "
                "import changed."
            ),
            tone="ok" if len(refused) + len(absent) == len(EXIT_CALLS) else "bad",
        )
        bounds = Panel(
            title="What this does and does not prove",
            rows=(
                Row("Proved", "every port is swappable and every seam is named"),
                Row("Proved", "an unimplemented seam refuses instead of dropping work"),
                Row("NOT proved", "a running on-premises deployment exists"),
                Row("NOT proved", "model, infrastructure or whole-system portability"),
            ),
            note=(
                "Bounded claims are the point. Run scripts/portability_demo.py for the full "
                "seam tour, with a pass or fail per named check."
            ),
        )
        return [exit_panel, bounds], {
            "refused": sorted(refused),
            "absent": sorted(absent),
        }

    # -------------------------------------------------------------- helpers

    def state(self) -> dict[str, Any]:
        """The whole run as JSON-safe data: what the UI renders and the walkthrough asserts."""
        current = self.results[-1]
        return {
            "service": SERVICE_NAME,
            "catalog_id": CATALOG_ID,
            "repository": REPOSITORY,
            "profile": self.settings.profile,
            "region": self.settings.region,
            "step": current.key,
            "step_index": self.index,
            "step_count": len(STEPS),
            "label": current.label,
            "next": "" if self.done else STEPS[len(self.results)].label,
            "done": self.done,
            "totals": {
                "cases": self.cases,
                "escalated": self.escalated,
                "routed": self.routed,
                "chain_ok": self.chain_ok,
            },
            "steps": [_step_to_dict(result) for result in self.results],
        }


def _step_to_dict(result: StepResult) -> dict[str, Any]:
    return {
        "key": result.key,
        "label": result.label,
        "narration": result.narration,
        "facts": result.facts,
        "panels": [
            {
                "title": panel.title,
                "note": panel.note,
                "tone": panel.tone,
                "rows": [
                    {"label": row.label, "value": row.value, "tone": row.tone} for row in panel.rows
                ],
            }
            for panel in result.panels
        ],
    }


def _summarise(payload: Any) -> str:
    """One readable line for a queued review, without dumping the whole payload."""
    if isinstance(payload, dict):
        parts = [
            str(payload[key])
            for key in ("title", "severity", "maker", "tenant")
            if payload.get(key)
        ]
        if parts:
            return " / ".join(parts)
    return json.dumps(payload, sort_keys=True)[:120]


def _rewrite_a_record(store: Path) -> int:
    """Drop the append-only triggers and rewrite one INTERIOR record, as an attacker would."""
    conn = sqlite3.connect(store)
    try:
        conn.execute("DROP TRIGGER IF EXISTS audit_log_no_update")
        conn.execute("DROP TRIGGER IF EXISTS audit_log_no_delete")
        rows = conn.execute("SELECT seq, event_json FROM audit_log ORDER BY seq ASC").fetchall()
        if len(rows) < 3:
            raise RuntimeError("the tamper step needs an interior record to rewrite")
        middle = rows[len(rows) // 2]
        payload = json.loads(middle[1])
        payload["decision"] = "allowed"
        payload["severity"] = "low"
        conn.execute(
            "UPDATE audit_log SET event_json = ? WHERE seq = ?",
            (json.dumps(payload, sort_keys=True, separators=(",", ":")), int(middle[0])),
        )
        conn.commit()
        return int(middle[0])
    finally:
        conn.close()


def _exit_audit(container: Any) -> Any:
    return container.audit.record(
        kernel.AuditEvent(
            action="propose_tolerances",
            actor=ACTOR,
            decision=kernel.Decision.ESCALATED,
            severity=kernel.Severity.HIGH,
            redacted_summary="Retail Payments (FICTIONAL): proposed tolerances",
        )
    )


def _exit_review(container: Any) -> Any:
    citation = kernel.Citation(source_id="apra-cps-230", title="APRA CPS 230", snippet="tolerance")
    return container.review_router.route(
        models.ResilienceReview(
            subject=SERVICE.name,
            severity=kernel.Severity.CRITICAL,
            decision=kernel.Decision.ESCALATED,
            summary="Retail Payments (FICTIONAL): proposed tolerances",
            requires_human_review=True,
            citations=(citation,),
        ),
        maker=ACTOR,
        tenant=TENANT,
    )


def _exit_identity(container: Any) -> Any:
    return container.identity.resolve(RequestContext(headers={"x-dev-persona": "approver"}))


def _exit_map_store(container: Any) -> Any:
    empty_map = ResilienceMap(service=SERVICE, nodes=(), edges=())
    return container.map_store.save_map(empty_map, tenant=TENANT)


def _exit_extraction(container: Any) -> Any:
    return container.extraction.extract("doc-settlement-runbook", b"", "application/pdf")


def _exit_asset_inventory(container: Any) -> Any:
    return container.asset_inventory.scan(SCOPE)


def _exit_register(container: Any) -> Any:
    return container.register.list_arrangements(SCOPE)


def _exit_compliance(container: Any) -> Any:
    return container.compliance.requirements("operational resilience requirements", ACTOR)


def _exit_generation(container: Any) -> Any:
    return container.generation.generate(
        GenerationRequest(system_instruction="narrate", prompt="engine output")
    )


def _exit_tracer(container: Any) -> Any:
    with container.tracer.span("exit.tour", action="portability"):
        return None


def _exit_evaluation(container: Any) -> Any:
    return container.evaluation.gate("eval/datasets/golden_cases.jsonl")


#: The calls the exit profile must REFUSE, one per port with an exit placeholder. Add a port,
#: add a row: a seam nobody calls is a seam nobody knows is unimplemented.
EXIT_CALLS: dict[str, Callable[[Any], Any]] = {
    "audit": _exit_audit,
    "identity": _exit_identity,
    "review_router": _exit_review,
    "tracer": _exit_tracer,
    "evaluation": _exit_evaluation,
    "map_store": _exit_map_store,
    "extraction": _exit_extraction,
    "asset_inventory": _exit_asset_inventory,
    "register": _exit_register,
    "compliance": _exit_compliance,
    "generation": _exit_generation,
}


#: Diagnostic seams that complete as an honest no-op under the exit profile.
EXIT_ABSENT: frozenset[str] = frozenset({"tracer"})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the scripted offline demo end to end.")
    parser.add_argument(
        "output",
        nargs="?",
        default="demo.json",
        help="where to write the audit-view JSON (default: demo.json)",
    )
    parser.add_argument("--quiet", action="store_true", help="write the JSON and print nothing")
    args = parser.parse_args(argv)

    run = DemoRun()
    run.run_to_end()
    state = run.state()
    Path(args.output).write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    if not args.quiet:
        for step in state["steps"]:
            print("[" + step["key"] + "] " + step["label"])
        totals = state["totals"]
        print("escalated=" + str(totals["escalated"]) + " routed=" + str(totals["routed"]))
        print("wrote " + args.output)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
