import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import logging
import psycopg
from src.config import settings
from src.services.database import database

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("apply_schema")


def apply_schema():
    schema_path = Path(__file__).resolve().parent.parent / "src" / "services" / "schema.sql"
    if not schema_path.exists():
        logger.error("Schema file not found at %s", schema_path)
        sys.exit(1)

    logger.info("Applying database schema from %s", schema_path)
    logger.info("Target database URL: %s", settings.database_url.split("@")[-1] if "@" in settings.database_url else "configured")

    if not database.is_reachable():
        logger.error(
            "Cannot connect to PostgreSQL at %s. Ensure PostgreSQL is reachable ('docker compose up -d' or Azure PostgreSQL firewall).",
            settings.database_url
        )
        sys.exit(1)

    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    # Migration adjustments for existing volumes
    migration_sql = """
    -- Ensure columns exist if table was already created in earlier volume init
    ALTER TABLE IF EXISTS mtg_rules ADD COLUMN IF NOT EXISTS rule_id VARCHAR(100);
    ALTER TABLE IF EXISTS mtg_rules ADD COLUMN IF NOT EXISTS embedding_model VARCHAR(100);
    ALTER TABLE IF EXISTS mtg_rules ADD COLUMN IF NOT EXISTS content_hash VARCHAR(64);
    ALTER TABLE IF EXISTS mtg_rules ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

    -- Ensure chat_sessions allows anonymous users
    ALTER TABLE IF EXISTS chat_sessions ALTER COLUMN user_id DROP NOT NULL;
    ALTER TABLE IF EXISTS chat_sessions ALTER COLUMN user_id SET DEFAULT 'anonymous';

    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'uq_mtg_rules_rule_id'
        ) THEN
            BEGIN
                ALTER TABLE mtg_rules ADD CONSTRAINT uq_mtg_rules_rule_id UNIQUE (rule_id);
            EXCEPTION
                WHEN duplicate_table OR duplicate_object OR duplicate_column THEN
                    NULL;
            END;
        END IF;
    END $$;

    CREATE INDEX IF NOT EXISTS idx_mtg_rules_rule_id ON mtg_rules (rule_id);
    """

    try:
        # Use a direct, unpooled connection with autocommit so CREATE EXTENSION executes cleanly
        with psycopg.connect(settings.database_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                logger.info("Executing base schema.sql DDL (including CREATE EXTENSION IF NOT EXISTS vector)...")
                cur.execute(schema_sql)
                logger.info("Executing idempotent migration guards...")
                cur.execute(migration_sql)

        if database.is_vector_ready():
            logger.info("✅ Schema, pgvector extension, and indexes applied successfully to PostgreSQL!")
        else:
            logger.warning("⚠️ Schema applied, but pgvector is not yet fully ready on this server.")
    finally:
        database.close()


if __name__ == "__main__":
    apply_schema()
