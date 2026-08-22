"""Canonical synthetic fixtures, shared by the unit and contract suites.

Every party is obviously fictional and every address is an ``.example`` domain. One canonical
escalating review and one PII-bearing review are enough for the contract suite: parity means the
SAME request through every implementation, so the request has one home rather than being retyped
per test.
"""

from __future__ import annotations

from operational_resilience_mapping.domain.kernel import Citation, Decision, Severity
from operational_resilience_mapping.domain.models import (
    ImportantBusinessService,
    ResilienceReview,
)

#: The verified principal the tests attribute work to (never a client-asserted actor).
ACTOR = "analyst@bank.example"

#: A tenant partition, so the outbound-review assertions are not all on the empty string.
TENANT = "demo-bank"

#: The scope the local fixture adapters answer for.
SCOPE = "projects/fictional"

#: The important business service the studio builds a map for in the tests.
SERVICE = ImportantBusinessService(
    id="ibs-retail-payments",
    name="Retail Payments (FICTIONAL)",
    criticality=Severity.CRITICAL,
)

_CITATION = Citation(source_id="apra-cps-230", title="APRA CPS 230", snippet="tolerance levels")

#: A consequential review that MUST escalate, so rule R8 routing applies.
ESCALATING_REVIEW = ResilienceReview(
    subject="Retail Payments (FICTIONAL)",
    severity=Severity.CRITICAL,
    decision=Decision.ESCALATED,
    summary="Retail Payments (FICTIONAL): proposed 4 impact tolerances under APRA_CPS230",
    requires_human_review=True,
    citations=(_CITATION,),
)

#: A planted identifier, so a redaction assertion has an independent literal to look for.
PLANTED_NRIC = "S1234567D"

#: A planted address, so the universal rows have an independent literal of their own.
PLANTED_EMAIL = "kai.tan@delta.example"

#: A service whose NAME carries personal data. The name is client-supplied over
#: ``POST /v1/tolerance`` and flows into the model prompt, the audit summary, the review subject
#: and the idempotency key, so it is the field that proves whether each boundary actually holds.
PII_SERVICE = ImportantBusinessService(
    id="ibs-retail-payments",
    name=f"Retail Payments owner NRIC {PLANTED_NRIC} mail {PLANTED_EMAIL} (FICTIONAL)",
    criticality=Severity.CRITICAL,
)

#: A citation whose LOCATOR and TITLE carry personal data, not only its snippet. The offline
#: compliance fixture answers static regulatory references, but the managed adapter reads Rsk1
#: over the wire and the ingestion path builds a locator from a document field, so a citation is
#: not structurally safe just because today's fixture happens to be.
PII_CITATION = Citation(
    source_id=f"rsk1:answer:{PLANTED_NRIC}",
    title=f"Requirement raised by {PLANTED_EMAIL}",
    snippet=f"owner NRIC {PLANTED_NRIC} must set the tolerance",
)

#: An escalating review that also carries personal data, for the redact-before-anything proofs.
PII_REVIEW = ResilienceReview(
    subject=f"Retail Payments owner NRIC {PLANTED_NRIC} (FICTIONAL)",
    severity=Severity.CRITICAL,
    decision=Decision.ESCALATED,
    summary=f"escalation raised by owner NRIC {PLANTED_NRIC}, mail {PLANTED_EMAIL}",
    requires_human_review=True,
    citations=(PII_CITATION,),
)
