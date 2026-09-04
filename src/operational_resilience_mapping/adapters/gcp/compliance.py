"""GCP CompliancePort: A2A client to compliance-advisory's compliance knowledge base.

No cloud SDK: the read is a plain HTTPS A2A call. It fails closed when ``compliance_url`` is
unconfigured, because inventing regulatory text is exactly what grounding forbids.
compliance-advisory is read as data; until the live feed is bound the offline fixture answer is the
frozen contract.
"""

from __future__ import annotations

from ...config import Settings
from ...domain.models import ComplianceAnswer


class CloudComplianceAdapter:
    """Fetch grounded regulatory text from compliance-advisory over A2A
    (refuses when unconfigured).
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def requirements(
        self, question: str, actor: str
    ) -> ComplianceAnswer:  # pragma: no cover - needs live compliance-advisory
        base_url = self._settings.compliance_url.strip()
        if not base_url:
            raise RuntimeError(
                "compliance_url is not configured, so compliance-advisory's knowledge base cannot "
                "be read. "
                "Set RSK1_COMPLIANCE_URL, or use the local profile's fixture answer."
            )
        raise NotImplementedError(
            "compliance-advisory compliance A2A client is wired when the feed exists"
        )
