from __future__ import annotations

import hashlib

from .models import Chunk, SourceDocument


def _stable_id(document: SourceDocument, chunk_index: int, text: str) -> str:
    basis = "|".join(
        [
            document.document_id or document.source,
            document.version or "",
            str(document.page or ""),
            str(chunk_index),
            text,
        ]
    )
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:32]


def chunk_document(document: SourceDocument, *, size: int, overlap: int) -> list[Chunk]:
    """Simple deterministic chunker.

    The exercise receives text, not PDF/DOCX bytes. Parsing/layout extraction belongs in a
    preceding ingestion stage; this function starts once reliable text + metadata exist.
    """
    text = " ".join(document.text.split())
    if not text:
        return []

    chunks: list[Chunk] = []
    start = 0
    index = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            boundary = text.rfind(" ", start, end)
            if boundary > start + size // 2:
                end = boundary

        piece = text[start:end].strip()
        if piece:
            metadata: dict[str, str | int] = {"source": document.source, "chunk_index": index}
            if document.page is not None:
                metadata["page"] = document.page
            if document.version:
                metadata["version"] = document.version
            if document.document_id:
                metadata["document_id"] = document.document_id
            chunks.append(
                Chunk(
                    id=_stable_id(document, index, piece),
                    text=piece,
                    metadata=metadata,
                )
            )
            index += 1

        if end >= len(text):
            break
        start = max(end - overlap, start + 1)

    return chunks
