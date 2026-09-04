"""GCP RegisterReadPort: A2A client to third-party-risk-ddq's Outsourcing Register.

No cloud SDK: the read is a plain HTTPS A2A call. It fails closed when ``register_url`` is
unconfigured, because inventing third parties would corrupt the resilience map. third-party-risk-ddq
is unbuilt in this wave, so a managed deployment binds this only once the live feed exists; until
then the offline fixture register is the frozen contract.
"""

from __future__ import annotations

from ...config import Settings
from ...domain.models import ThirdPartyArrangement


class CloudRegisterAdapter:
    """Read third-party arrangements from third-party-risk-ddq over A2A
    (refuses when unconfigured).
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def list_arrangements(
        self, scope: str
    ) -> tuple[ThirdPartyArrangement, ...]:  # pragma: no cover - needs live third-party-risk-ddq
        base_url = self._settings.register_url.strip()
        if not base_url:
            raise RuntimeError(
                "register_url is not configured, so third-party-risk-ddq's Outsourcing Register "
                "cannot be read. "
                "Set RGC8_REGISTER_URL, or use the local profile's fixture register."
            )
        raise NotImplementedError(
            "third-party-risk-ddq register A2A client is wired when the feed exists"
        )
