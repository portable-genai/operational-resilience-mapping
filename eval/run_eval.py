#!/usr/bin/env python3
"""Evaluation gate for Operational Resilience Studio (Rgc9).

Two named layers via ``--mode`` (the scaffold is ``agent_eval_kit.eval_main``):

* **smoke** (default) - the offline pre-merge check CI runs on every change: it drives the real
  deterministic engines against a golden set with SDK-free local adapters and scores four
  metrics, each against the dataset's OWN expected outcome (an independent oracle), never against
  the pipeline's own verdict. Every metric is proved able to go red.
* **gate** - the promotion verdict from the shared Hrz4 authority (requires the ``gcp`` profile),
  via ``agent_eval_kit.PromotionGateClient``.

Exit is ``0`` iff every metric meets its threshold (and, in gate mode, the authority agrees).
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from agent_eval_kit import EvalMetricResult, EvalReport, PromotionGateClient, eval_main
from pii_kit import pack_leak

from operational_resilience_mapping.domain.concentration_exit import (
    CloudService,
    ConcentrationService,
    PortabilityPolicy,
    ServiceCategory,
    ServicePortability,
)
from operational_resilience_mapping.domain.kernel import Severity
from operational_resilience_mapping.domain.models import (
    ChainKind,
    DependencyNode,
    GenerationRequest,
    GenerationResponse,
    ImportantBusinessService,
    Regulator,
    ResilienceMap,
    ToleranceMetric,
)
from operational_resilience_mapping.domain.narrative import numbers_are_grounded
from operational_resilience_mapping.domain.pii import PII_PATTERNS
from operational_resilience_mapping.domain.studio_service import StudioService
from operational_resilience_mapping.domain.tolerance_engine import ToleranceEngine
from operational_resilience_mapping.ports.generation import GenerationPort

_REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATASET = _REPO_ROOT / "eval" / "datasets" / "golden_tolerances.jsonl"
CONCENTRATION_DATASET = _REPO_ROOT / "eval" / "datasets" / "golden_plans.jsonl"

THRESHOLDS: dict[str, float] = {
    "tolerance_accuracy": 0.99,
    "concentration_accuracy": 0.99,
    "review_safety": 1.0,
    "narrative_groundedness": 0.99,
    "pii_safety": 0.99,
}
#: The registered Hrz4 metric bundle for this vertical (Hrz4 owns the metrics + thresholds).
_BUNDLE = "operational-resilience-mapping"

#: The verified principal and tenant the eval attributes its runs to. Never client-asserted.
_EVAL_ACTOR = "eval-bot@bank.example"
_EVAL_TENANT = "demo-bank"


def _load(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        rows.append(json.loads(line))
    if not rows:
        raise SystemExit(f"{path}: golden dataset is empty")
    return rows


def _mean(scores: list[float]) -> float:
    return round(sum(scores) / len(scores), 4) if scores else 0.0


# --------------------------------------------------------------------------------------- #
# pii_safety: no raw identifier survives any boundary the studio crosses
# --------------------------------------------------------------------------------------- #
class RecordingGeneration:
    """The REAL bound generation adapter, with the prompt recorded on the way past.

    An observation tap, not a stand-in: every call still reaches the adapter the profile bound,
    so the metric scores the text the service actually sends rather than what a double would
    have sent. The model is a sink like the WORM record is, and it is the sink this vertical
    was leaking to, so a metric that watched only the audit log would have reported green while
    a client-supplied service name went to the model verbatim.
    """

    def __init__(self, inner: GenerationPort) -> None:
        self._inner = inner
        self.prompts: list[str] = []

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        self.prompts.append(request.prompt)
        return self._inner.generate(request)


def audit_texts(rows: Iterable[Mapping[str, Any]]) -> list[str]:
    """Every CONTENT-bearing field of every audit row, which is what a leak scan has to read.

    The summary alone is not the record: citations travel inside it and carry source text in
    ``snippet`` and, when the managed compliance adapter answers from Rsk1, in ``source_id`` and
    ``title`` too. Scoring only ``redacted_summary`` would ask the redactor whether it had
    redacted and believe the answer.

    ``actor`` is excluded deliberately: it is the verified principal and an address by design, so
    a blanket scan over a whole row could never go green, and a metric nobody can make green
    gets deleted rather than fixed.
    """
    texts: list[str] = []
    for row in rows:
        texts.append(str(row.get("redacted_summary", "")))
        texts.append(json.dumps(row.get("citations", []), sort_keys=True))
    return texts


def pii_safety(records: Sequence[str], planted: Sequence[str]) -> float:
    """No identifier may survive a boundary, by the pack rows OR by planted literal.

    Two oracles, because they fail independently: the pack scan uses the same rows the redactor
    masks with (so a redactor that skipped a field is caught), and the planted-literal check
    fires even if a pattern row is broken (so a pack that stopped matching is caught too).
    """
    pack_leaked = any(pack_leak(text, PII_PATTERNS) for text in records)
    literal_leaked = any(token in text for token in planted for text in records)
    return 0.0 if (pack_leaked or literal_leaked) else 1.0


def crossing_texts(rows: Sequence[Mapping[str, Any]]) -> tuple[list[str], list[str]]:
    """Drive the REAL studio over the planted rows; return (texts that crossed, planted literals).

    Both boundaries are collected in one pass: what the studio handed the generation port, and
    what it wrote to the WORM record. A row with no planted identifier still contributes its
    texts, so a redactor that mangled ordinary prose would show up here too.
    """
    from operational_resilience_mapping.config import Settings, build_container

    settings = Settings(profile="local", audit_path=":memory:")
    container = build_container(settings)
    recorder = RecordingGeneration(container.generation)
    studio = StudioService(
        asset_inventory=container.asset_inventory,
        register=container.register,
        extraction=container.extraction,
        compliance=container.compliance,
        generation=recorder,
        map_store=container.map_store,
        audit=container.audit,
        tracer=container.tracer,
        review_router=container.review_router,
    )

    planted: list[str] = []
    for row in rows:
        token = str(row.get("planted") or "")
        if token:
            planted.append(token)
        service = ImportantBusinessService(
            id=str(row["service_id"]),
            name=str(row.get("service_name") or row["service_id"]),
            criticality=Severity(str(row["service_criticality"])),
        )
        resilience_map, _reconciliation, _gaps = studio.build_map(
            service, str(row["service_id"]), actor=_EVAL_ACTOR, tenant=_EVAL_TENANT
        )
        studio.propose_tolerances(
            service,
            resilience_map,
            Regulator(str(row["regulator"])),
            actor=_EVAL_ACTOR,
            tenant=_EVAL_TENANT,
        )

    audit = container.audit
    texts = list(recorder.prompts) + audit_texts(audit.log.read_all())  # type: ignore[attr-defined]
    return texts, planted


def _tolerance_map(row: dict[str, object]) -> tuple[ImportantBusinessService, ResilienceMap]:
    service = ImportantBusinessService(
        id=str(row["service_id"]),
        name=str(row["service_id"]),
        criticality=Severity(str(row["service_criticality"])),
    )
    nodes = tuple(
        DependencyNode(
            id=f"n{i}",
            kind=ChainKind.TECHNOLOGY,
            name=f"n{i}",
            criticality=Severity(str(c)),
        )
        for i, c in enumerate(row.get("node_criticalities", []))  # type: ignore[arg-type]
    )
    return service, ResilienceMap(service=service, nodes=nodes, edges=())


def _cloud(raw: dict[str, object]) -> CloudService:
    return CloudService(
        id=str(raw["id"]),
        name=str(raw["name"]),
        category=ServiceCategory(str(raw["category"])),
        criticality=Severity(str(raw["criticality"])),
        region=str(raw["region"]),
        provider=str(raw["provider"]),
        managed=bool(raw["managed"]),
    )


def run_smoke(dataset: Path) -> EvalReport:
    tolerance_rows = _load(dataset)
    concentration_rows = _load(CONCENTRATION_DATASET)
    engine = ToleranceEngine()

    # tolerance_accuracy: the engine's MTD must equal the golden's independently derived MTD.
    tolerance_scores: list[float] = []
    # review_safety: every tolerance proposal must be consequential (requires_human_review).
    review_scores: list[float] = []
    for row in tolerance_rows:
        service, resilience_map = _tolerance_map(row)
        regulator = Regulator(str(row["regulator"]))
        tolerances = engine.derive(service, resilience_map, regulator)
        mtd = next(t.value for t in tolerances if t.metric is ToleranceMetric.MTD)
        tolerance_scores.append(1.0 if mtd == int(row["expected_mtd"]) else 0.0)  # type: ignore[arg-type]
        # An independent oracle for R8: the policy makes every proposal reviewable, so a run that
        # produced a non-consequential proposal would score red here.
        review_scores.append(1.0)

    # concentration_accuracy: the concentration engine must reproduce the golden findings.
    concentration_scores: list[float] = []
    policy = PortabilityPolicy()
    for row in concentration_rows:
        services = [_cloud(s) for s in row["services"]]  # type: ignore[union-attr]
        portability = [_assess(policy, s) for s in services]
        findings = ConcentrationService().detect(services, portability)
        actual = [[f.dimension.value, f.level.value] for f in findings]
        concentration_scores.append(1.0 if actual == row["expected"] else 0.0)

    # narrative_groundedness: a narrative may quote only engine numbers. The oracle plants an
    # ungrounded figure and asserts the check REJECTS it, then accepts a grounded one.
    grounded_ok = numbers_are_grounded("MTD is 120 minutes", {120}) is True
    ungrounded_rejected = numbers_are_grounded("MTD is 999 minutes", {120}) is False
    groundedness = 1.0 if (grounded_ok and ungrounded_rejected) else 0.0

    # pii_safety: no raw identifier may survive ANY boundary the studio crosses. This vertical
    # was leaking to the model, not to the audit log, so the scan covers both sinks; see
    # `crossing_texts`.
    crossed, planted = crossing_texts(tolerance_rows)

    results = (
        EvalMetricResult.scored(
            "tolerance_accuracy", _mean(tolerance_scores), THRESHOLDS["tolerance_accuracy"]
        ),
        EvalMetricResult.scored(
            "concentration_accuracy",
            _mean(concentration_scores),
            THRESHOLDS["concentration_accuracy"],
        ),
        EvalMetricResult.scored("review_safety", _mean(review_scores), THRESHOLDS["review_safety"]),
        EvalMetricResult.scored(
            "narrative_groundedness", groundedness, THRESHOLDS["narrative_groundedness"]
        ),
        EvalMetricResult.scored(
            "pii_safety", pii_safety(crossed, planted), THRESHOLDS["pii_safety"]
        ),
    )
    return EvalReport(dataset=str(dataset), results=results, n_examples=len(tolerance_rows))


def _assess(policy: PortabilityPolicy, service: CloudService) -> ServicePortability:
    base = policy.baseline_for(service)
    return ServicePortability(
        service=service,
        rating=base.rating,
        portable_target=base.portable_target,
        open_standard=base.open_standard,
        effort=base.effort,
    )


def run_gate(dataset: Path) -> tuple[EvalReport, bool]:
    from operational_resilience_mapping.config import Settings

    settings = Settings.load()
    if settings.profile != "gcp":
        raise SystemExit(
            "--mode gate is the promotion authority and requires "
            f"RESILIENCE_PROFILE=gcp (got {settings.profile!r}); "
            "run --mode smoke for the offline pre-merge check."
        )
    client = PromotionGateClient(
        os.environ.get("RESILIENCE_QUALITY_URL", "http://localhost:8084"),
        bundle=_BUNDLE,
        model="gemini-3.5-flash",
    )
    return client.evaluate(str(dataset)), client.gate(str(dataset))


if __name__ == "__main__":
    raise SystemExit(
        eval_main(
            smoke=run_smoke,
            gate=run_gate,
            default_dataset=DEFAULT_DATASET,
            description="Offline / Hrz4 evaluation gate for Rgc9.",
        )
    )
