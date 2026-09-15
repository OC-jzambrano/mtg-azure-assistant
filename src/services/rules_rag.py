import logging
import re
from typing import List, Optional, Any

from src.config import settings
from src.services.rules_loader import RuleChunk, load_rule_chunks
from src.services.embeddings import EmbeddingService, embedding_service as default_embedding_service
from src.repositories.rules_repository import RulesRepository

logger = logging.getLogger("mtg_assistant.rules_rag")

# Re-export RuleChunk for backwards compatibility
__all__ = ["RuleChunk", "RulesRAGStore"]


class RulesRAGStore:
    """
    RAG store for MTG Official Comprehensive Rules.
    Primary Path: Vector similarity search via PostgreSQL + pgvector (HNSW cosine ops).
    Fallback Path: Resilient canonical in-memory lexical retrieval engine.
    """

    def __init__(
        self,
        data_path: Optional[str] = None,
        repository: Optional[RulesRepository] = None,
        embedding_service: Optional[EmbeddingService] = None,
        backend: Optional[str] = None,
    ):
        self.data_path = data_path or settings.rules_data_path
        self.repository = repository or RulesRepository()
        self.embedding_service = embedding_service or default_embedding_service
        self.backend = backend or settings.rag_backend
        self.last_backend_used: str = "lexical_fallback"

        # Load canonical chunks for lexical fallback and offline readiness
        self.chunks: List[RuleChunk] = load_rule_chunks(self.data_path)

    def vector_backend_available(self) -> bool:
        """
        Determines whether the pgvector backend and embedding service are healthy.
        Honors RAG_BACKEND configuration ('auto', 'pgvector', 'lexical').
        """
        if self.backend == "lexical":
            return False

        if not self.embedding_service.is_available():
            return False

        if not self.repository.is_available():
            return False

        return True

    def retrieve_rules(self, query: str, top_k: int = 3) -> List[RuleChunk]:
        """
        Retrieves the most relevant rules for a given question.
        Attempts pgvector cosine search first. Gracefully degrades to lexical fallback
        if credentials, network, or database are unavailable.
        """
        if self.vector_backend_available():
            try:
                query_vector = self.embedding_service.embed_query(query)
                vector_results = self.repository.vector_search(query_vector, top_k=top_k)
                if vector_results:
                    self.last_backend_used = "pgvector"
                    logger.debug("Retrieved %d rules using pgvector search.", len(vector_results))
                    return vector_results
            except Exception as exc:
                logger.warning(
                    "pgvector retrieval failed; activating lexical fallback. Error: %s",
                    exc,
                )

        self.last_backend_used = "lexical_fallback"
        return self._retrieve_lexical(query, top_k=top_k)

    def _retrieve_lexical(self, query: str, top_k: int = 3) -> List[RuleChunk]:
        """
        Lexical relevance scoring based on MTG domain terms, numbers, and concepts.
        Guarantees 100% offline functionality and zero unhandled errors.
        """
        if not self.chunks:
            return []

        query_lower = query.lower()
        query_words = set(re.findall(r"\w+", query_lower))

        scored_chunks: List[tuple[float, RuleChunk]] = []

        # Key domain keywords weight
        weights = {
            "mana": 3.0,
            "maná": 3.0,
            "reserva": 2.5,
            "pool": 2.5,
            "fases": 3.0,
            "fase": 3.0,
            "turno": 2.5,
            "pasos": 2.0,
            "combate": 2.5,
            "dañar primero": 4.0,
            "daño primero": 4.0,
            "first strike": 4.0,
            "ninjutsu": 4.0,
            "ninja": 3.0,
            "bloqueada": 2.5,
            "daño": 2.0,
            "robar": 2.5,
            "ward": 4.0,
            "guardia": 4.0,
            "reemplazo": 4.0,
            "replacement": 4.0,
            "instead": 3.0,
            "en vez de": 3.0,
            "contrarresta": 3.0,
            "counter": 3.0,
            "objetivo": 2.5,
            "target": 2.5,
        }

        for chunk in self.chunks:
            haystack = (
                f"{chunk.title} {chunk.content} {chunk.category} {chunk.rule_number}".lower()
            )
            score = 0.0

            # Match exact rule number (e.g. 106, 500, 702.48)
            if chunk.rule_number in query_lower:
                score += 10.0

            # Match keyword weights
            for kw, weight in weights.items():
                if kw in query_lower and kw in haystack:
                    score += weight * 2.0

            # Overlap of words
            chunk_words = set(re.findall(r"\w+", haystack))
            common = query_words.intersection(chunk_words)
            score += len(common) * 0.5

            if score > 0:
                scored_chunks.append((score, chunk))

        # Sort by relevance
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        top_results = [chunk for _, chunk in scored_chunks[:top_k]]

        # Fallback if query was too generic
        if not top_results and self.chunks:
            top_results = self.chunks[:top_k]

        return top_results
