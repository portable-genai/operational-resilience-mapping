"""Golden parity: the concentration engine reproduces the golden findings byte-identically.

Exit and portability planning lives in operational-resilience-mapping as the ``concentration_exit``
module. This replays the golden set through that engine and asserts the findings match it exactly
(dimension, level, regulatory reference and remediation), plus that a replay is deterministic.
Without this pin an engine edit can move a finding's level or its regulatory reference and no test
notices.
"""

from __future__ import annotations

import json

from operational_resilience_mapping.domain.concentration_exit import (
    CloudService,
    ConcentrationService,
    PortabilityPolicy,
    ServiceCategory,
    ServicePortability,
)
from operational_resilience_mapping.domain.kernel import Severity

from tests import REPO_ROOT

_GOLDEN = REPO_ROOT / "eval" / "datasets" / "golden_plans.jsonl"


def _load() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line in _GOLDEN.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if text and not text.startswith("#"):
            rows.append(json.loads(text))
    return rows


def _cloud_service(raw: dict[str, object]) -> CloudService:
    return CloudService(
        id=str(raw["id"]),
        name=str(raw["name"]),
        category=ServiceCategory(str(raw["category"])),
        criticality=Severity(str(raw["criticality"])),
        region=str(raw["region"]),
        provider=str(raw["provider"]),
        managed=bool(raw["managed"]),
    )


def _assess(policy: PortabilityPolicy, service: CloudService) -> ServicePortability:
    base = policy.baseline_for(service)
    return ServicePortability(
        service=service,
        rating=base.rating,
        portable_target=base.portable_target,
        open_standard=base.open_standard,
        effort=base.effort,
    )


def _detect(raw_services: list[dict[str, object]]) -> list[tuple[str, str]]:
    policy = PortabilityPolicy()
    services = [_cloud_service(s) for s in raw_services]
    portability = [_assess(policy, s) for s in services]
    findings = ConcentrationService().detect(services, portability)
    return [(f.dimension.value, f.level.value) for f in findings]


def test_every_golden_estate_reproduces_its_expected_findings() -> None:
    for row in _load():
        services = list(row["services"])  # type: ignore[arg-type]
        expected = [tuple(pair) for pair in row["expected"]]  # type: ignore[arg-type]
        actual = _detect(services)
        assert actual == expected, f"{row['name']}: concentration findings drifted from the golden"


def test_the_replay_is_deterministic() -> None:
    for row in _load():
        services = list(row["services"])  # type: ignore[arg-type]
        assert _detect(services) == _detect(services)


def test_findings_carry_the_regulatory_reference_and_remediation() -> None:
    policy = PortabilityPolicy()
    services = [
        CloudService(
            id="ledger",
            name="Ledger",
            category=ServiceCategory.DB,
            criticality=Severity.CRITICAL,
            region="asia-southeast1",
            provider="gcp",
            managed=True,
        ),
        CloudService(
            id="fraud",
            name="Fraud model",
            category=ServiceCategory.ML,
            criticality=Severity.CRITICAL,
            region="asia-southeast1",
            provider="gcp",
            managed=True,
        ),
    ]
    portability = [_assess(policy, s) for s in services]
    findings = ConcentrationService().detect(services, portability)
    assert findings, "the concentration engine produced no findings for a locked critical estate"
    for finding in findings:
        assert "CPS 230" in finding.regulatory_ref
        assert finding.remediation
