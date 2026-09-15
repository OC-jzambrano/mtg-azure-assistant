from __future__ import annotations

from collections.abc import Sequence

import chromadb

from .models import Chunk, RetrievedChunk


class ChromaVectorStore:
    def __init__(self, *, path: str, collection_name: str) -> None:
        self._client = chromadb.PersistentClient(path=path)
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert(self, chunks: Sequence[Chunk], embeddings: Sequence[list[float]]) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have the same length")
        if not chunks:
            return
        self._collection.upsert(
            ids=[chunk.id for chunk in chunks],
            documents=[chunk.text for chunk in chunks],
            metadatas=[chunk.metadata for chunk in chunks],
            embeddings=list(embeddings),
        )

    def query(self, embedding: list[float], *, top_k: int) -> list[RetrievedChunk]:
        if self._collection.count() == 0:
            return []
        raw = self._collection.query(
            query_embeddings=[embedding],
            n_results=min(top_k, self._collection.count()),
            include=["documents", "metadatas", "distances"],
        )
        docs = (raw.get("documents") or [[]])[0]
        metas = (raw.get("metadatas") or [[]])[0]
        distances = (raw.get("distances") or [[]])[0]
        ids = (raw.get("ids") or [[]])[0]

        return [
            RetrievedChunk(
                id=str(chunk_id),
                text=str(document),
                distance=float(distance),
                metadata=dict(metadata or {}),
            )
            for chunk_id, document, metadata, distance in zip(ids, docs, metas, distances, strict=True)
        ]
