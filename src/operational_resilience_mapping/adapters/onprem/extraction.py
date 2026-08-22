"""On-prem DocumentExtractionPort: fail-fast portability placeholder (P-12)."""

from __future__ import annotations

from ...config import Settings
from ...domain.models import ExtractedDocument


class OnPremExtractionAdapter:
    """Satisfies DocumentExtractionPort but refuses: the client wires its own OCR / extraction."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def extract(self, document: str, content: bytes, mime_type: str) -> ExtractedDocument:
        raise NotImplementedError(
            "on-prem extraction is a portability placeholder: bind the client's own extractor"
        )
