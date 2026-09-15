import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import logging
from typing import List, Dict, Tuple
from src.config import settings
from src.services.database import database
from src.services.embeddings import embedding_service
from src.services.rules_loader import (
    load_rule_chunks,
    build_embedding_text,
    calculate_content_hash,
    RuleChunk,
)
from src.repositories.rules_repository import RulesRepository

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ingest_rules")


def ingest_rules():
    logger.info("Starting MTG Rules Ingestion Pipeline...")
    logger.info("Source rules path: %s", settings.rules_data_path)

    # 1. Load canonical rule chunks
    chunks: List[RuleChunk] = load_rule_chunks(settings.rules_data_path)
    total_loaded = len(chunks)
    logger.info("Loaded %d rule chunks from canonical dataset.", total_loaded)

    if total_loaded == 0:
        logger.warning("No rule chunks found to ingest.")
        return

    # 2. Verify database connectivity
    if not database.is_available():
        logger.error(
            "Cannot connect to PostgreSQL at %s. Start docker-compose before ingesting rules.",
            settings.database_url,
        )
        sys.exit(1)

    repository = RulesRepository(db=database)

    # 3. Check existing content hashes for idempotency
    existing_hashes = repository.get_existing_hashes()
    logger.info("Retrieved %d existing rule hashes from PostgreSQL.", len(existing_hashes))

    to_process_chunks: List[RuleChunk] = []
    to_process_texts: List[str] = []
    to_process_hashes: List[str] = []

    new_embeddings = 0
    updated = 0
    skipped_unchanged = 0

    for chunk in chunks:
        norm_text = build_embedding_text(chunk)
        c_hash = calculate_content_hash(norm_text)

        if chunk.rule_id in existing_hashes and existing_hashes[chunk.rule_id] == c_hash:
            skipped_unchanged += 1
        else:
            if chunk.rule_id in existing_hashes:
                updated += 1
            else:
                new_embeddings += 1

            to_process_chunks.append(chunk)
            to_process_texts.append(norm_text)
            to_process_hashes.append(c_hash)

    # 4. Generate embeddings for new or updated chunks
    embeddings = None
    embedding_model = None

    if to_process_chunks:
        if embedding_service.is_available():
            logger.info(
                "Embedding service is active (%s). Generating vectors for %d chunks...",
                embedding_service.deployment,
                len(to_process_chunks),
            )
            embeddings = embedding_service.embed_documents(to_process_texts, batch_size=50)
            embedding_model = embedding_service.deployment
        else:
            logger.warning(
                "EmbeddingService unavailable (no credentials). "
                "Ingesting %d chunks without vectors (lexical fallback will remain active).",
                len(to_process_chunks),
            )
            embeddings = [None] * len(to_process_chunks)

        # 5. Batch upsert into PostgreSQL
        logger.info("Upserting %d rule chunks into PostgreSQL...", len(to_process_chunks))
        repository.upsert_rules(
            chunks=to_process_chunks,
            embeddings=embeddings,
            embedding_model=embedding_model,
            content_hashes=to_process_hashes,
        )

    # 6. Final report (matching DoD specification)
    print("\n" + "=" * 60)
    print("📚 MTG RULES INGESTION REPORT")
    print("=" * 60)
    print(f"Rules loaded:       {total_loaded}")
    print(f"New embeddings:     {new_embeddings}")
    print(f"Updated:            {updated}")
    print(f"Skipped unchanged:  {skipped_unchanged}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    try:
        ingest_rules()
    finally:
        database.close()
