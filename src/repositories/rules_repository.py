import logging
from typing import List, Dict, Optional, Any
from psycopg.types.json import Jsonb

from src.services.database import Database, database
from src.services.rules_loader import RuleChunk

logger = logging.getLogger("mtg_assistant.rules_repository")


class RulesRepository:
    """
    Dedicated PostgreSQL + pgvector repository for Magic: The Gathering rules.
    Decoupled from embedding generation, file parsing, and LLM reasoning.
    """

    def __init__(self, db: Optional[Database] = None):
        self.db = db or database

    def is_available(self) -> bool:
        """Checks if the underlying database is reachable."""
        return self.db.is_available()

    def get_existing_hashes(self) -> Dict[str, str]:
        """
        Retrieves a mapping of {rule_id: content_hash} for all stored rules.
        Used by the ingestion pipeline for idempotency detection.
        """
        hashes: Dict[str, str] = {}
        with self.db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT rule_id, content_hash FROM mtg_rules WHERE content_hash IS NOT NULL;"
                )
                for row in cur.fetchall():
                    hashes[row[0]] = row[1]
        return hashes

    def count_rules(self) -> int:
        """Returns the total number of rules in mtg_rules."""
        with self.db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM mtg_rules;")
                res = cur.fetchone()
                return res[0] if res else 0

    def count_with_embeddings(self) -> int:
        """Returns the number of rules with non-null embeddings."""
        with self.db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM mtg_rules WHERE embedding IS NOT NULL;")
                res = cur.fetchone()
                return res[0] if res else 0

    def upsert_rule(
        self,
        chunk: RuleChunk,
        embedding: Optional[List[float]] = None,
        embedding_model: Optional[str] = None,
        content_hash: Optional[str] = None,
    ) -> bool:
        """Upserts a single rule chunk into mtg_rules table."""
        res = self.upsert_rules(
            chunks=[chunk],
            embeddings=[embedding] if embedding is not None else None,
            embedding_model=embedding_model,
            content_hashes=[content_hash] if content_hash is not None else None,
        )
        return bool(res.get("total", 0) > 0)

    def upsert_rules(
        self,
        chunks: List[RuleChunk],
        embeddings: Optional[List[Optional[List[float]]]] = None,
        embedding_model: Optional[str] = None,
        content_hashes: Optional[List[Optional[str]]] = None,
    ) -> Dict[str, int]:
        """
        Idempotently batch-upserts rule chunks into PostgreSQL.
        Uses ON CONFLICT (rule_id) DO UPDATE.
        Returns a dict with {"inserted": count, "updated": count, "total": count}.
        """
        if not chunks:
            return {"inserted": 0, "updated": 0, "total": 0}

        upsert_query = """
        INSERT INTO mtg_rules (
            rule_id,
            rule_number,
            category,
            title,
            content,
            metadata,
            embedding,
            embedding_model,
            content_hash,
            updated_at
        )
        VALUES (
            %(rule_id)s,
            %(rule_number)s,
            %(category)s,
            %(title)s,
            %(content)s,
            %(metadata)s,
            %(embedding)s,
            %(embedding_model)s,
            %(content_hash)s,
            NOW()
        )
        ON CONFLICT (rule_id)
        DO UPDATE SET
            rule_number = EXCLUDED.rule_number,
            category = EXCLUDED.category,
            title = EXCLUDED.title,
            content = EXCLUDED.content,
            metadata = EXCLUDED.metadata,
            embedding = COALESCE(EXCLUDED.embedding, mtg_rules.embedding),
            embedding_model = COALESCE(EXCLUDED.embedding_model, mtg_rules.embedding_model),
            content_hash = COALESCE(EXCLUDED.content_hash, mtg_rules.content_hash),
            updated_at = NOW()
        RETURNING (xmax = 0) AS is_insert;
        """

        inserted = 0
        updated = 0

        with self.db.connection() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    for i, chunk in enumerate(chunks):
                        emb = embeddings[i] if embeddings and i < len(embeddings) else None
                        c_hash = (
                            content_hashes[i]
                            if content_hashes and i < len(content_hashes)
                            else None
                        )

                        cur.execute(
                            upsert_query,
                            {
                                "rule_id": chunk.rule_id,
                                "rule_number": chunk.rule_number,
                                "category": chunk.category,
                                "title": chunk.title,
                                "content": chunk.content,
                                "metadata": Jsonb(chunk.metadata),
                                "embedding": emb,
                                "embedding_model": embedding_model,
                                "content_hash": c_hash,
                            },
                        )
                        row = cur.fetchone()
                        if row and row[0]:
                            inserted += 1
                        else:
                            updated += 1

        return {"inserted": inserted, "updated": updated, "total": inserted + updated}

    def vector_search(self, query_embedding: List[float], top_k: int = 3) -> List[RuleChunk]:
        """
        Executes a vector cosine similarity search over mtg_rules using the <=> operator.
        Returns top_k RuleChunk objects with normalized similarity score (1 - distance).
        """
        search_query = """
        SELECT
            rule_id,
            rule_number,
            category,
            title,
            content,
            metadata,
            1 - (embedding <=> %(query_embedding)s::vector) AS score
        FROM mtg_rules
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> %(query_embedding)s::vector
        LIMIT %(top_k)s;
        """

        results: List[RuleChunk] = []
        with self.db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    search_query,
                    {"query_embedding": query_embedding, "top_k": top_k},
                )
                rows = cur.fetchall()
                for row in rows:
                    rule_id, rule_number, category, title, content, meta, score = row
                    results.append(
                        RuleChunk(
                            rule_id=rule_id,
                            rule_number=rule_number,
                            category=category,
                            title=title,
                            content=content,
                            citation=f"Magic Comprehensive Rules (CR {rule_number}) - {title}",
                            score=float(score) if score is not None else 1.0,
                            metadata=meta if isinstance(meta, dict) else {},
                        )
                    )

        return results
