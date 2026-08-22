"""Local DocumentExtractionPort: return the fictional fixture corpus (SDK-free).

Answers offline. A known fixture document id returns its structured extract; any other id returns
a minimal extract carrying the raw text, so the reconciler still has something to ground against.
"""

from __future__ import annotations

from ...config import Settings
from ...domain.models import ExtractedDocument
from . import _fixtures


class LocalExtractionAdapter:
    """Extract structured fields from the offline fixture corpus."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._by_id = {doc.document_id: doc for doc in _fixtures.DOCUMENTS}

    def extract(self, document: str, content: bytes, mime_type: str) -> ExtractedDocument:
        known = self._by_id.get(document)
        if known is not None:
            return known
        text = content.decode("utf-8", errors="replace") if content else ""
        return ExtractedDocument(
            document_id=document,
            mime_type=mime_type,
            fields=(("name", document),),
            full_text=text,
        )
