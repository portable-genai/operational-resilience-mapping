"""Shared conversion from an escalated result to an ``review-kit`` Review payload.

Lives in the adapter layer, not the pure domain, because it depends on the kit. The subject, summary
and every citation snippet are redacted BEFORE they leave the process (the same
redact-before-anything rule the audit write obeys), using the shared ``pii-kit``, so no raw
identifier reaches human-review-console over the wire; human-review-console redacts again before its
own audit write (defence in depth). ``maker`` and ``tenant`` are asserted here and trusted by
human-review-console because the caller is an authenticated S2S service; per-hop on-behalf-of token
exchange is the deferred next layer.
"""

from __future__ import annotations

import re

from pii_kit import NATIONAL_ID_PATTERNS, UNIVERSAL_PATTERNS, national_patterns_for
from pii_kit import redact as pii_redact
from review_kit import Citation as KitCitation
from review_kit import Review

from ..domain.kernel import Severity
from ..domain.models import ResilienceReview

#: Cap the citations carried on the wire: enough for a reviewer to trace the decision without
#: copying the whole evidence set into the console.
_MAX_CITATIONS = 8

#: The console is a SHARED sink: a case filed in one market may still quote another market's
#: national id, so the payload is scrubbed against every jurisdiction's rows plus the universal
#: email/phone rows, whatever this deployment's own ``domain.pii.JURISDICTIONS`` selects.
_ALL_PATTERNS = (
    *national_patterns_for(tuple(NATIONAL_ID_PATTERNS.keys())),
    *UNIVERSAL_PATTERNS,
)

#: Bands that demand dual control (two approvals) rather than a single checker.
_DUAL_CONTROL = (Severity.CRITICAL,)


def _redact(text: str) -> str:
    """Mask every jurisdiction's identifiers plus email/phone, and normalise whitespace."""
    return re.sub(r"\s+", " ", pii_redact(text, _ALL_PATTERNS)).strip()


def _kit_citations(result: ResilienceReview) -> tuple[KitCitation, ...]:
    """Every field of every citation is masked, not only the snippet.

    A locator can be built from client text (an compliance-advisory answer reference, an ingested
    document
    field), so masking only the snippet let the identifier cross to the shared console in the
    field named like a key. De-duplication keys off the REDACTED locator, so two citations that
    differ only in a masked identifier collapse to one rather than both crossing the wire.
    """
    seen: set[str] = set()
    out: list[KitCitation] = []
    for citation in result.citations:
        source_id = _redact(citation.source_id)
        if source_id in seen:
            continue
        seen.add(source_id)
        out.append(
            KitCitation(
                source_id=source_id,
                title=_redact(citation.title),
                snippet=_redact(citation.snippet),
            )
        )
        if len(out) >= _MAX_CITATIONS:
            break
    return tuple(out)


def result_to_review(result: ResilienceReview, *, maker: str, tenant: str = "") -> Review:
    """Build the review a producer submits to human-review-console when a result escalates.

    The subject is redacted ONCE and reused for the case reference and the idempotency key, so no
    raw identifier reaches the wire even through a derived field: a service label should never
    carry personal data, but the redaction must hold whether or not it does.
    """
    subject = _redact(result.subject)
    return Review(
        action="operational_resilience_mapping:resilience",
        subject=subject,
        maker=maker,
        tenant=tenant,
        summary=_redact(result.summary),
        severity=result.severity.value,
        required_approvals=2 if result.severity in _DUAL_CONTROL else 1,
        sod_group="operational_resilience_mapping-maker-checker",
        case_ref=subject,
        # Producer-owned, tenant-scoped key so a retried delivery is idempotent at the console.
        source_key=f"operational-resilience-mapping:{subject}:{result.severity.value}",
        citations=_kit_citations(result),
    )
