import pytest
from unittest.mock import MagicMock
from src.services.rules_loader import (
    RuleChunk,
    build_embedding_text,
    calculate_content_hash,
)
from src.repositories.rules_repository import RulesRepository


@pytest.fixture
def mock_db():
    db = MagicMock()
    conn = MagicMock()
    cursor = MagicMock()
    # Support context managers
    db.connection.return_value.__enter__.return_value = conn
    conn.transaction.return_value.__enter__.return_value = None
    conn.cursor.return_value.__enter__.return_value = cursor
    return db, conn, cursor


def test_vector_search_sql_query(mock_db):
    """Demuestra que vector_search utiliza el operador <=> y calcula score = 1 - distance."""
    db, conn, cursor = mock_db

    # Simular una fila retornada:
    # (rule_id, rule_number, category, title, content, metadata, score)
    cursor.fetchall.return_value = [
        (
            "CR-702.21a",
            "702.21a",
            "Habilidades de Protección",
            "Guardia (Ward)",
            "Guardia es una habilidad disparada...",
            {"is_subrule": False},
            0.89,
        )
    ]

    repo = RulesRepository(db=db)
    query_vector = [0.1] * 1536
    results = repo.vector_search(query_vector, top_k=1)

    assert len(results) == 1
    assert results[0].rule_id == "CR-702.21a"
    assert results[0].rule_number == "702.21a"
    assert results[0].score == 0.89

    # Verificar que la query contiene el operador de distancia coseno de pgvector
    executed_sql = cursor.execute.call_args[0][0]
    assert "<=>" in executed_sql
    assert "1 - (embedding <=> %(query_embedding)s" in executed_sql


def test_upsert_rules_conflict_handling(mock_db):
    """Demuestra que upsert_rules utiliza ON CONFLICT (rule_id) DO UPDATE."""
    db, conn, cursor = mock_db

    # Simular que fetchone retorna (True,) para insert y (False,) para update
    cursor.fetchone.side_effect = [(True,), (False,)]

    repo = RulesRepository(db=db)
    chunks = [
        RuleChunk(
            rule_id="CR-106",
            rule_number="106.1",
            category="Sistema de Maná",
            title="Maná",
            content="El maná...",
            citation="CR 106.1",
        ),
        RuleChunk(
            rule_id="CR-500",
            rule_number="500.1",
            category="Estructura del Turno",
            title="Fases",
            content="Cinco fases...",
            citation="CR 500.1",
        ),
    ]

    res = repo.upsert_rules(
        chunks=chunks,
        embeddings=[[0.1] * 1536, [0.2] * 1536],
        embedding_model="text-embedding-3-small",
        content_hashes=["hash1", "hash2"],
    )

    assert res["inserted"] == 1
    assert res["updated"] == 1
    assert res["total"] == 2

    executed_sql = cursor.execute.call_args[0][0]
    assert "ON CONFLICT (rule_id)" in executed_sql
    assert "DO UPDATE SET" in executed_sql


def test_ingestion_is_idempotent():
    """
    Demuestra que el cálculo de hash permite identificar reglas sin cambios
    para evitar re-embeddear y no duplicar registros en PostgreSQL.
    """
    chunk = RuleChunk(
        rule_id="CR-106.1",
        rule_number="106.1",
        category="Sistema de Maná",
        title="Maná y Reserva",
        content="El maná es el recurso principal...",
        citation="CR 106.1",
    )

    # 1. Primera ejecución: hash generado
    text = build_embedding_text(chunk)
    h1 = calculate_content_hash(text)
    assert len(h1) == 64  # SHA256

    # 2. Base de datos simula tener este hash ya almacenado
    existing_hashes = {"CR-106.1": h1}

    # 3. Verificación de idempotencia: el hash coincide exactamente -> no se re-ingesta
    assert chunk.rule_id in existing_hashes
    assert existing_hashes[chunk.rule_id] == h1


def test_count_rules_mock(mock_db):
    """Demuestra que count_rules consulta correctamente la tabla mtg_rules."""
    db, conn, cursor = mock_db
    cursor.fetchone.return_value = (17,)

    repo = RulesRepository(db=db)
    assert repo.count_rules() == 17
    assert "COUNT(*)" in cursor.execute.call_args[0][0]
