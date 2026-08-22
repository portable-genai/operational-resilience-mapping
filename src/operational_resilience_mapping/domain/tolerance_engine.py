"""ToleranceEngine: deterministic impact-tolerance derivation (slice 5).

Pure stdlib. Per-regulator tolerance packs are carried as DATA (the parameter shapes for
APRA CPS 230, DORA and the UK operational-resilience regime: the MTD / RTO / RPO minute bounds
and the customer-harm threshold form). The engine derives candidate tolerances deterministically
from the chain criticality plus the pack rules; the model drafts only the justification
narrative and never a number.

The chain criticality is the worst criticality across the important business service and every
node in its resilience map: a chain is only as resilient as its most critical dependency, so a
CRITICAL vendor buried under a HIGH service pulls the whole chain to CRITICAL. Every pack value
is adopter-owned data here, so swapping in a client's board-approved numbers is a data edit, not
a code change, and the eval oracle re-derives the expected values from the SAME packs
independently of the engine.
"""

from __future__ import annotations

from dataclasses import dataclass

from .kernel import SEVERITY_RANK, Citation, Severity
from .models import (
    ImpactTolerance,
    ImportantBusinessService,
    Regulator,
    ResilienceMap,
    ToleranceMetric,
)


@dataclass(frozen=True, slots=True)
class TolerancePack:
    """One regulator's impact-tolerance parameter shape (carried as data)."""

    regulator: Regulator
    reference: str
    mtd_by_criticality: dict[Severity, int]  # maximum tolerable disruption, minutes
    rpo_by_criticality: dict[Severity, int]  # recovery point objective, minutes
    harm_by_criticality: dict[Severity, int]  # customers-affected harm threshold, count
    rto_numerator: int = 1  # RTO = MTD * rto_numerator // rto_denominator
    rto_denominator: int = 2


_APRA = TolerancePack(
    regulator=Regulator.APRA_CPS230,
    reference="APRA CPS 230 para 36 (tolerance levels for disruption to critical operations)",
    mtd_by_criticality={
        Severity.CRITICAL: 120,
        Severity.HIGH: 240,
        Severity.MEDIUM: 720,
        Severity.LOW: 1440,
    },
    rpo_by_criticality={
        Severity.CRITICAL: 5,
        Severity.HIGH: 15,
        Severity.MEDIUM: 60,
        Severity.LOW: 240,
    },
    harm_by_criticality={
        Severity.CRITICAL: 100,
        Severity.HIGH: 1000,
        Severity.MEDIUM: 10000,
        Severity.LOW: 100000,
    },
)

_DORA = TolerancePack(
    regulator=Regulator.DORA,
    reference="DORA Art. 11 (ICT business-continuity, recovery objectives for critical functions)",
    mtd_by_criticality={
        Severity.CRITICAL: 60,
        Severity.HIGH: 180,
        Severity.MEDIUM: 480,
        Severity.LOW: 960,
    },
    rpo_by_criticality={
        Severity.CRITICAL: 2,
        Severity.HIGH: 10,
        Severity.MEDIUM: 30,
        Severity.LOW: 120,
    },
    harm_by_criticality={
        Severity.CRITICAL: 50,
        Severity.HIGH: 500,
        Severity.MEDIUM: 5000,
        Severity.LOW: 50000,
    },
)

_UK = TolerancePack(
    regulator=Regulator.UK_OPRES,
    reference="UK PRA SS1/21 / FCA PS21/3 (impact tolerances for important business services)",
    mtd_by_criticality={
        Severity.CRITICAL: 240,
        Severity.HIGH: 480,
        Severity.MEDIUM: 1440,
        Severity.LOW: 2880,
    },
    rpo_by_criticality={
        Severity.CRITICAL: 15,
        Severity.HIGH: 30,
        Severity.MEDIUM: 120,
        Severity.LOW: 480,
    },
    harm_by_criticality={
        Severity.CRITICAL: 200,
        Severity.HIGH: 2000,
        Severity.MEDIUM: 20000,
        Severity.LOW: 200000,
    },
)

#: The shipped packs, keyed by regulator. Adopter-owned: swap the numbers, keep the engine.
TOLERANCE_PACKS: dict[Regulator, TolerancePack] = {
    Regulator.APRA_CPS230: _APRA,
    Regulator.DORA: _DORA,
    Regulator.UK_OPRES: _UK,
}


class ToleranceEngine:
    """Derive candidate impact tolerances deterministically from chain criticality + packs."""

    def __init__(self, packs: dict[Regulator, TolerancePack] | None = None) -> None:
        self._packs = dict(packs or TOLERANCE_PACKS)

    def chain_criticality(
        self,
        service: ImportantBusinessService,
        resilience_map: ResilienceMap,
    ) -> Severity:
        """The worst criticality across the service and every node in its chain."""
        worst = service.criticality
        for node in resilience_map.nodes:
            if SEVERITY_RANK[node.criticality] > SEVERITY_RANK[worst]:
                worst = node.criticality
        return worst

    def derive(
        self,
        service: ImportantBusinessService,
        resilience_map: ResilienceMap,
        regulator: Regulator,
        *,
        citations: tuple[Citation, ...] = (),
    ) -> list[ImpactTolerance]:
        """Derive the MTD / RTO / RPO / harm tolerances for ``service`` under ``regulator``."""
        pack = self._packs[regulator]
        criticality = self.chain_criticality(service, resilience_map)
        mtd = pack.mtd_by_criticality[criticality]
        rto = mtd * pack.rto_numerator // pack.rto_denominator
        rpo = pack.rpo_by_criticality[criticality]
        harm = pack.harm_by_criticality[criticality]
        basis = (
            f"{pack.reference}; chain criticality {criticality.value} "
            f"(worst of the service and its {resilience_map.n_nodes} mapped dependencies)"
        )

        def tol(metric: ToleranceMetric, value: int, unit: str) -> ImpactTolerance:
            return ImpactTolerance(
                service_id=service.id,
                metric=metric,
                value=value,
                unit=unit,
                regulator=regulator,
                basis=basis,
                citations=citations,
            )

        return [
            tol(ToleranceMetric.MTD, mtd, "minutes"),
            tol(ToleranceMetric.RTO, rto, "minutes"),
            tol(ToleranceMetric.RPO, rpo, "minutes"),
            tol(ToleranceMetric.HARM_THRESHOLD, harm, "customers"),
        ]
