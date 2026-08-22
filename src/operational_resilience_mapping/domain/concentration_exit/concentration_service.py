"""Deterministic concentration / lock-in detection.

Given the cloud services in use and their portability assessments, it deterministically detects
concentration / provider-lock-in findings along four dimensions:

* SINGLE_PROVIDER : all critical services sit on one provider.
* SINGLE_REGION   : all critical services sit in one region.
* CRITICAL_SERVICE: a business-critical service is LOCKED (no open-standard exit).
* DATA_GRAVITY    : a large managed data / analytics store is hard to move.

Each finding maps to the outsourcing rule (APRA CPS 230 / MAS / HKMA) whose expectation the
concentration offends. Pure standard library; no cloud / framework imports. The detector emits
no citations, so replaying it produces byte-identical findings; the studio grounds each finding
on the compliance answer's citations afterwards.
"""

from __future__ import annotations

from ..kernel import SEVERITY_RANK, Severity
from .models import (
    CloudService,
    ConcentrationDimension,
    ConcentrationFinding,
    RiskLevel,
    ServiceCategory,
    ServicePortability,
)

_REGULATORY_REF: dict[ConcentrationDimension, str] = {
    ConcentrationDimension.SINGLE_PROVIDER: (
        "APRA CPS 230 (concentration risk in material service providers); "
        "MAS / HKMA outsourcing (over-reliance on a single provider)"
    ),
    ConcentrationDimension.SINGLE_REGION: (
        "APRA CPS 230 (geographic concentration); MAS / HKMA outsourcing (resilience)"
    ),
    ConcentrationDimension.CRITICAL_SERVICE: (
        "APRA CPS 230 (documented, tested exit for material arrangements); "
        "MAS / HKMA outsourcing (ability to exit a critical outsourcing)"
    ),
    ConcentrationDimension.DATA_GRAVITY: (
        "APRA CPS 230 (portability of critical data); MAS / HKMA outsourcing (data exit)"
    ),
}

_REMEDIATION: dict[ConcentrationDimension, str] = {
    ConcentrationDimension.SINGLE_PROVIDER: (
        "Establish a documented multi-provider / portable target for material services "
        "and a tested exit runbook."
    ),
    ConcentrationDimension.SINGLE_REGION: (
        "Add an in-country secondary region or an on-prem / Google Distributed Cloud "
        "failover for critical services."
    ),
    ConcentrationDimension.CRITICAL_SERVICE: (
        "Re-platform the locked critical service to an open standard, or accept and "
        "document the residual risk with board sign-off."
    ),
    ConcentrationDimension.DATA_GRAVITY: (
        "Adopt open data formats and rehearse a bulk export so the data store can be "
        "moved within the recovery-time objective."
    ),
}

#: Categories whose managed services carry meaningful data gravity.
_DATA_CATEGORIES = (ServiceCategory.DB, ServiceCategory.ANALYTICS, ServiceCategory.STORAGE)


class ConcentrationService:
    """Deterministically detect concentration / lock-in findings. Pure, testable."""

    def detect(
        self,
        services: list[CloudService],
        portability: list[ServicePortability],
    ) -> list[ConcentrationFinding]:
        """Return the concentration findings for ``services`` and their portability."""
        findings: list[ConcentrationFinding] = []
        critical = [s for s in services if self._is_critical(s)]

        findings.extend(self._single_provider(critical))
        findings.extend(self._single_region(critical))
        findings.extend(self._critical_locked(portability))
        findings.extend(self._data_gravity(services))
        return findings

    def _single_provider(self, critical: list[CloudService]) -> list[ConcentrationFinding]:
        providers = {s.provider for s in critical}
        if len(critical) >= 2 and len(providers) == 1:
            provider = next(iter(providers))
            return [
                self._finding(
                    ConcentrationDimension.SINGLE_PROVIDER,
                    RiskLevel.HIGH,
                    f"All {len(critical)} critical services run on a single provider "
                    f"('{provider}'), so an outage or exit affects every critical service "
                    f"at once.",
                )
            ]
        return []

    def _single_region(self, critical: list[CloudService]) -> list[ConcentrationFinding]:
        regions = {s.region for s in critical if s.region}
        if len(critical) >= 2 and len(regions) == 1:
            region = next(iter(regions))
            return [
                self._finding(
                    ConcentrationDimension.SINGLE_REGION,
                    RiskLevel.MEDIUM,
                    f"All critical services sit in a single region ('{region}'); a regional "
                    f"failure has no in-country failover.",
                )
            ]
        return []

    def _critical_locked(self, portability: list[ServicePortability]) -> list[ConcentrationFinding]:
        out: list[ConcentrationFinding] = []
        for sp in portability:
            if sp.is_locked and self._is_critical(sp.service):
                out.append(
                    self._finding(
                        ConcentrationDimension.CRITICAL_SERVICE,
                        RiskLevel.CRITICAL,
                        f"Critical service '{sp.service.name}' is LOCKED to the provider "
                        f"with no open-standard exit, breaching the documented-exit "
                        f"expectation for a material outsourcing.",
                    )
                )
        return out

    def _data_gravity(self, services: list[CloudService]) -> list[ConcentrationFinding]:
        heavy = [
            s
            for s in services
            if s.managed and s.category in _DATA_CATEGORIES and self._is_critical(s)
        ]
        if heavy:
            names = ", ".join(s.name for s in heavy)
            return [
                self._finding(
                    ConcentrationDimension.DATA_GRAVITY,
                    RiskLevel.MEDIUM,
                    f"Critical managed data stores ({names}) carry data gravity that can "
                    f"exceed the recovery-time objective during an exit.",
                )
            ]
        return []

    @staticmethod
    def _is_critical(service: CloudService) -> bool:
        return SEVERITY_RANK[service.criticality] >= SEVERITY_RANK[Severity.HIGH]

    @staticmethod
    def _finding(
        dimension: ConcentrationDimension,
        level: RiskLevel,
        detail: str,
    ) -> ConcentrationFinding:
        return ConcentrationFinding(
            dimension=dimension,
            level=level,
            detail=detail,
            regulatory_ref=_REGULATORY_REF[dimension],
            remediation=_REMEDIATION[dimension],
            citations=(),
        )
