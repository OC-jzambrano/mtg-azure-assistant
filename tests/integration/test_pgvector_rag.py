import pytest
from src.services.database import database
from src.services.rules_loader import RuleChunk
from src.services.embeddings import embedding_service
from src.repositories.rules_repository import RulesRepository
from src.services.rules_rag import RulesRAGStore


@pytest.mark.integration
def test_pgvector_cosine_retrieval():
    """
    Live integration test against PostgreSQL + pgvector.
    Verifies that the <=> operator and HNSW indexing calculate real cosine similarity
    without requiring Azure OpenAI credentials.
    """
    if not database.is_available():
        pytest.skip("PostgreSQL is not available; skipping live pgvector integration test.")

    repo = RulesRepository(db=database)

    # 1. Tres vectores ortogonales deterministas (1536 dimensiones)
    mana_vector = [1.0] + [0.0] * 1535
    combat_vector = [0.0, 1.0] + [0.0] * 1534
    ward_vector = [0.0, 0.0, 1.0] + [0.0] * 1533

    test_chunks = [
        RuleChunk(
            rule_id="TEST-CR-106-MANA",
            rule_number="106.99",
            category="Test Sistema de Maná",
            title="Test Maná Pool",
            content="Regla de prueba de maná",
            citation="Test CR 106.99",
        ),
        RuleChunk(
            rule_id="TEST-CR-506-COMBAT",
            rule_number="506.99",
            category="Test Fase de Combate",
            title="Test Combate",
            content="Regla de prueba de combate",
            citation="Test CR 506.99",
        ),
        RuleChunk(
            rule_id="TEST-CR-702-WARD",
            rule_number="702.99",
            category="Test Guardia",
            title="Test Guardia Ward",
            content="Regla de prueba de guardia",
            citation="Test CR 702.99",
        ),
    ]

    try:
        # 2. Insertar reglas de prueba con vectores
        repo.upsert_rules(
            chunks=test_chunks,
            embeddings=[mana_vector, combat_vector, ward_vector],
            embedding_model="test-deterministic",
            content_hashes=["hash_mana", "hash_combat", "hash_ward"],
        )

        # 3. Query con vector similar al de maná: [0.99, 0.01, 0, ...]
        query_mana = [0.99, 0.01] + [0.0] * 1534
        results_mana = repo.vector_search(query_mana, top_k=1)

        assert len(results_mana) == 1
        assert results_mana[0].rule_id == "TEST-CR-106-MANA"
        assert results_mana[0].rule_number == "106.99"
        assert results_mana[0].score > 0.98

        # 4. Query con vector similar a ward: [0.0, 0.05, 0.99, ...]
        query_ward = [0.0, 0.05, 0.99] + [0.0] * 1533
        results_ward = repo.vector_search(query_ward, top_k=1)

        assert len(results_ward) == 1
        assert results_ward[0].rule_id == "TEST-CR-702-WARD"
        assert results_ward[0].score > 0.98

    finally:
        # Cleanup test records
        with database.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM mtg_rules WHERE rule_id IN ('TEST-CR-106-MANA', 'TEST-CR-506-COMBAT', 'TEST-CR-702-WARD');"
                )
                conn.commit()


@pytest.mark.integration
def test_live_embedding_retrieval():
    """
    Live integration test against PostgreSQL + Azure OpenAI embeddings.
    Runs only if both PostgreSQL and OpenAI credentials are configured.
    """
    if not database.is_available():
        pytest.skip("PostgreSQL is not available; skipping live embedding retrieval test.")

    if not embedding_service.is_available():
        pytest.skip("Embedding service credentials not configured; skipping live test.")

    rag_store = RulesRAGStore(backend="pgvector")
    results = rag_store.retrieve_rules("¿Cómo funciona el maná?", top_k=3)

    assert rag_store.last_backend_used == "pgvector"
    assert len(results) > 0
    assert any("106" in r.rule_number for r in results)
