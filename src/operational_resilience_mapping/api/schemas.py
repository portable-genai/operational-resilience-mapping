"""API request/response schemas (Pydantic) mapped to/from the pure-domain models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from ..config import OFFLINE_STUB_MODEL
from ..domain.models import ToleranceProposal


class CitationModel(BaseModel):
    source_id: str
    title: str
    snippet: str = ""


class ToleranceRequest(BaseModel):
    scope: str
    service_id: str
    service_name: str
    regulator: str
    #: Optional document ids to ingest into the resilience map before proposing tolerances.
    document_ids: list[str] = []


class ToleranceItem(BaseModel):
    metric: str
    value: int
    unit: str
    regulator: str
    basis: str


class ToleranceResponse(BaseModel):
    service_id: str
    regulator: str
    tolerances: list[ToleranceItem]
    narrative: str
    requires_human_review: bool
    #: Where the escalation WENT (rule R8): the human-review-console review id or the local queue
    #: reference. A tolerance proposal is always consequential, so this is empty only when the
    #: hand-off did not reach the console, and ``review_routing`` says why.
    review_ref: str = ""
    #: What happened to the hand-off: routed, failed, off or not_required. ``failed`` means the
    #: proposal is NOT queued for review, and the console says so.
    review_routing: Literal["routed", "failed", "off", "not_required"] = "not_required"
    citations: list[CitationModel] = []

    @classmethod
    def from_domain(
        cls,
        proposal: ToleranceProposal,
        *,
        review_ref: str = "",
        review_routing: str = "not_required",
    ) -> ToleranceResponse:
        return cls(
            service_id=proposal.service_id,
            regulator=proposal.regulator.value,
            tolerances=[
                ToleranceItem(
                    metric=t.metric.value,
                    value=t.value,
                    unit=t.unit,
                    regulator=t.regulator.value,
                    basis=t.basis,
                )
                for t in proposal.tolerances
            ],
            narrative=proposal.narrative,
            requires_human_review=proposal.requires_human_review,
            review_ref=review_ref,
            review_routing=review_routing,  # type: ignore[arg-type]
            citations=[
                CitationModel(source_id=c.source_id, title=c.title, snippet=c.snippet)
                for c in proposal.citations
            ],
        )


class HealthResponse(BaseModel):
    status: str
    profile: str
    region: str
    #: What the UI's model pill states before any answer: where the runtime sits and which model
    #: the bound generator calls. Both are read off the service because the browser cannot know
    #: either. Once a request is answered, the pill shows that response's ``X-Answered-By``.
    runtime: str = "local"  # "gcp" | "local"
    generator_model: str = OFFLINE_STUB_MODEL
