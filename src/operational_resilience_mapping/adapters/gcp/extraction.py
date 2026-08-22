"""GCP DocumentExtractionPort: Document AI (SDK imports stay lazy)."""

from __future__ import annotations

from ...config import Settings
from ...domain.models import ExtractedDocument


class CloudExtractionAdapter:
    """Extract structured fields with Document AI. The SDK import lives inside the method so the
    offline profiles import this module with no cloud SDK installed.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def extract(
        self, document: str, content: bytes, mime_type: str
    ) -> ExtractedDocument:  # pragma: no cover - needs live GCP
        from google.cloud import documentai

        _ = (documentai, document, content, mime_type)
        raise NotImplementedError("Document AI extraction is wired at deploy time")
