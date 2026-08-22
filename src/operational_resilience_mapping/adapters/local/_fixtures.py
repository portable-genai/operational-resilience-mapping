"""Deterministic, obviously fictional fixture corpus for the offline (local) adapter family.

All parties are synthetic (``.example`` domains, invented names). This is the estate the offline
profile ingests: a technology inventory (asset-inventory port), an outsourcing register (Rgc8 A2A
port), a document corpus (extraction port) and a grounded compliance answer (Rsk1 A2A port). It
is also the frozen contract for the two unbuilt siblings (Rgc8, Rsk1): the contract fixture tests
assert these shapes so the live feeds can be swapped in without a code change.
"""

from __future__ import annotations

from ...domain.kernel import Citation, Severity
from ...domain.models import (
    ComplianceAnswer,
    ExtractedDocument,
    ImportantBusinessService,
    ResourceConfig,
    ThirdPartyArrangement,
)

#: The important business service the demo / eval build a resilience map for.
SERVICE = ImportantBusinessService(
    id="ibs-retail-payments",
    name="Retail Payments (FICTIONAL)",
    criticality=Severity.CRITICAL,
)

#: Technology dependencies returned by a scan of the fictional estate.
RESOURCES: tuple[ResourceConfig, ...] = (
    ResourceConfig(
        id="svc-ledger-db",
        kind="database",
        name="Ledger database",
        provider="gcp",
        region="asia-southeast1",
        criticality=Severity.CRITICAL,
        managed=True,
    ),
    ResourceConfig(
        id="svc-payments-api",
        kind="compute",
        name="Payments API",
        provider="gcp",
        region="asia-southeast1",
        criticality=Severity.HIGH,
        managed=False,
    ),
    ResourceConfig(
        id="svc-fraud-scorer",
        kind="ml",
        name="Fraud scoring model",
        provider="gcp",
        region="asia-southeast1",
        criticality=Severity.HIGH,
        managed=True,
    ),
    ResourceConfig(
        id="svc-object-store",
        kind="storage",
        name="Statement object store",
        provider="gcp",
        region="asia-southeast1",
        criticality=Severity.MEDIUM,
        managed=True,
    ),
)

#: Third-party arrangements read from Rgc8's Outsourcing Register (fixture).
ARRANGEMENTS: tuple[ThirdPartyArrangement, ...] = (
    ThirdPartyArrangement(
        id="tp-card-network",
        vendor_name="Meridian Card Network (FICTIONAL)",
        service="Card authorisation switch",
        criticality=Severity.CRITICAL,
        region="asia-southeast1",
        material=True,
    ),
    ThirdPartyArrangement(
        id="tp-cloud-provider",
        vendor_name="Cumulus Cloud (FICTIONAL)",
        service="Managed cloud platform",
        criticality=Severity.CRITICAL,
        region="asia-southeast1",
        material=True,
    ),
    ThirdPartyArrangement(
        id="tp-kyc-bureau",
        vendor_name="Veritas KYC Bureau (FICTIONAL)",
        service="Identity verification",
        criticality=Severity.HIGH,
        region="asia-southeast1",
        material=True,
    ),
)

#: Extracted document corpus (process runbook, org chart) for the process / people chains.
DOCUMENTS: tuple[ExtractedDocument, ...] = (
    ExtractedDocument(
        document_id="doc-settlement-runbook",
        mime_type="application/pdf",
        fields=(("name", "End-of-day settlement process"), ("criticality", "high")),
        full_text=(
            "The end-of-day settlement process reconciles the ledger against the card network "
            "and depends on the payments operations team and the settlement window."
        ),
    ),
    ExtractedDocument(
        document_id="doc-ops-org-chart",
        mime_type="application/pdf",
        fields=(("name", "Payments operations team"), ("criticality", "high")),
        full_text=(
            "The payments operations team owns the settlement runbook and the incident bridge."
        ),
    ),
)

#: The grounded regulatory answer the compliance port returns (fixture text + citations).
COMPLIANCE_ANSWER = ComplianceAnswer(
    question=(
        "What do APRA CPS 230, DORA and the UK operational-resilience regime require for impact "
        "tolerances and third-party concentration for a critical business service?"
    ),
    answer=(
        "APRA CPS 230 requires the entity to set tolerance levels for disruption to each critical "
        "operation and to manage material service-provider concentration; DORA requires ICT "
        "business-continuity and recovery objectives for critical functions; the UK regime "
        "requires impact tolerances for important business services and testing against them."
    ),
    citations=(
        Citation(
            source_id="apra-cps-230",
            title="APRA CPS 230 Operational Risk Management",
            snippet="Set tolerance levels for disruption to critical operations (para 36).",
        ),
        Citation(
            source_id="eu-dora-art-11",
            title="DORA Article 11 (ICT business continuity)",
            snippet="Recovery objectives for critical or important functions.",
        ),
        Citation(
            source_id="uk-pra-ss1-21",
            title="UK PRA SS1/21 / FCA PS21/3",
            snippet="Set impact tolerances for important business services and test against them.",
        ),
    ),
    confidence=0.9,
)
