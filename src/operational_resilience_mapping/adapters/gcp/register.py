"""GCP RegisterReadPort: A2A client to Rgc8's Outsourcing Register.

No cloud SDK: the read is a plain HTTPS A2A call. It fails closed when ``register_url`` is
unconfigured, because inventing third parties would corrupt the resilience map. Rgc8 is unbuilt
in this wave, so a managed deployment binds this only once the live feed exists; until then the
offline fixture register is the frozen contract.
"""

from __future__ import annotations

from ...config import Settings
from ...domain.models import ThirdPartyArrangement


class CloudRegisterAdapter:
    """Read third-party arrangements from Rgc8 over A2A (refuses when unconfigured)."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def list_arrangements(
        self, scope: str
    ) -> tuple[ThirdPartyArrangement, ...]:  # pragma: no cover - needs live Rgc8
        base_url = self._settings.register_url.strip()
        if not base_url:
            raise RuntimeError(
                "register_url is not configured, so Rgc8's Outsourcing Register cannot be read. "
                "Set RGC8_REGISTER_URL, or use the local profile's fixture register."
            )
        raise NotImplementedError("Rgc8 register A2A client is wired when the feed exists")
