"""DocumentExtractionPort: the source-document extraction boundary (slice 4).

Takes credit-memo-drafting's extraction shape: ``extract(document, content, mime_type)`` returning
structured fields plus the full text. The offline family returns a fictional fixture corpus (process
docs, runbooks and org charts), the managed family calls Document AI with lazy imports, the on-prem
family refuses. The model later proposes edges from the extracted text; the engine reconciles.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..domain.models import ExtractedDocument


@runtime_checkable
class DocumentExtractionPort(Protocol):
    def extract(self, document: str, content: bytes, mime_type: str) -> ExtractedDocument:
        """Extract structured fields plus full text from one source document."""
        ...
