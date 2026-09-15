import pytest
from unittest.mock import MagicMock
from src.services.rules_loader import RuleChunk
from src.services.rules_rag import RulesRAGStore


@pytest.fixture
def sample_vector_chunks():
    return [
        RuleChunk(
            rule_id="CR-106",
            rule_number="106.1",
            category="Sistema de Maná",
            title="Maná y Reserva de Maná",
            content="El maná es el recurso principal...",
            citation="Magic Comprehensive Rules (CR 106.1) - Maná y Reserva de Maná",
            score=0.92,
        ),
        RuleChunk(
            rule_id="CR-106_106.2",
            rule_number="106.2",
            category="Sistema de Maná",
            title="Tipos y Colores de Maná",
            content="Hay cinco colores de maná...",
            citation="Magic Comprehensive Rules (CR 106.2) - Tipos y Colores de Maná",
            score=0.88,
        ),
        RuleChunk(
            rule_id="CR-106_202.1",
            rule_number="202.1",
            category="Sistema de Maná",
            title="Coste de Maná vs Valor de Maná",
            content="El coste de maná de una carta...",
            citation="Magic Comprehensive Rules (CR 202.1) - Coste de Maná vs Valor de Maná",
            score=0.81,
        ),
    ]


def test_rule_retrieval_uses_vector_backend(sample_vector_chunks):
    """Demuestra que pgvector es el camino primario cuando la base de datos y embeddings están disponibles."""
    mock_repo = MagicMock()
    mock_repo.is_available.return_value = True
    mock_repo.vector_search.return_value = sample_vector_chunks

    mock_embeddings = MagicMock()
    mock_embeddings.is_available.return_value = True
    mock_embeddings.embed_query.return_value = [0.1] * 1536

    rag_store = RulesRAGStore(
        repository=mock_repo,
        embedding_service=mock_embeddings,
        backend="auto",
    )

    results = rag_store.retrieve_rules("¿Cómo funciona el maná?", top_k=3)

    assert rag_store.last_backend_used == "pgvector"
    assert len(results) == 3
    mock_embeddings.embed_query.assert_called_once_with("¿Cómo funciona el maná?")
    mock_repo.vector_search.assert_called_once()
    assert results[0].rule_number == "106.1"
    assert results[0].score == 0.92


def test_rule_retrieval_returns_top_k(sample_vector_chunks):
    """Demuestra que el retrieval respeta estrictamente el parámetro top_k."""
    mock_repo = MagicMock()
    mock_repo.is_available.return_value = True
    mock_repo.vector_search.return_value = sample_vector_chunks[:2]

    mock_embeddings = MagicMock()
    mock_embeddings.is_available.return_value = True
    mock_embeddings.embed_query.return_value = [0.1] * 1536

    rag_store = RulesRAGStore(
        repository=mock_repo,
        embedding_service=mock_embeddings,
        backend="auto",
    )

    results = rag_store.retrieve_rules("¿Cómo funciona el maná?", top_k=2)

    assert len(results) == 2
    mock_repo.vector_search.assert_called_once_with([0.1] * 1536, top_k=2)


def test_rule_retrieval_preserves_rule_number(sample_vector_chunks):
    """Demuestra que los RuleChunks recuperados preservan rule_number y citation exacta."""
    mock_repo = MagicMock()
    mock_repo.is_available.return_value = True
    mock_repo.vector_search.return_value = sample_vector_chunks

    mock_embeddings = MagicMock()
    mock_embeddings.is_available.return_value = True
    mock_embeddings.embed_query.return_value = [0.1] * 1536

    rag_store = RulesRAGStore(
        repository=mock_repo,
        embedding_service=mock_embeddings,
        backend="auto",
    )

    results = rag_store.retrieve_rules("maná", top_k=3)

    assert results[0].rule_number == "106.1"
    assert "CR 106.1" in results[0].citation
    assert results[1].rule_number == "106.2"
    assert "CR 106.2" in results[1].citation


def test_rag_falls_back_when_embedding_unavailable():
    """Demuestra resiliencia: si el servicio de embeddings no está configurado, activa fallback léxico."""
    mock_repo = MagicMock()
    mock_repo.is_available.return_value = True

    mock_embeddings = MagicMock()
    mock_embeddings.is_available.return_value = False  # Sin API keys

    rag_store = RulesRAGStore(
        repository=mock_repo,
        embedding_service=mock_embeddings,
        backend="auto",
    )

    results = rag_store.retrieve_rules("¿Cómo funciona el maná?", top_k=3)

    assert rag_store.last_backend_used == "lexical_fallback"
    assert len(results) > 0
    # Valida que el fallback léxico recuperó la regla canónica de maná (CR 106.1)
    assert any(r.rule_number.startswith("106") for r in results)
    mock_embeddings.embed_query.assert_not_called()
    mock_repo.vector_search.assert_not_called()


def test_rag_falls_back_when_database_fails():
    """Demuestra resiliencia: si PostgreSQL o vector_search arrojan error, activa fallback léxico."""
    mock_repo = MagicMock()
    mock_repo.is_available.return_value = True
    mock_repo.vector_search.side_effect = ConnectionError("PostgreSQL connection timeout")

    mock_embeddings = MagicMock()
    mock_embeddings.is_available.return_value = True
    mock_embeddings.embed_query.return_value = [0.1] * 1536

    rag_store = RulesRAGStore(
        repository=mock_repo,
        embedding_service=mock_embeddings,
        backend="auto",
    )

    results = rag_store.retrieve_rules("Dime las fases del turno", top_k=3)

    assert rag_store.last_backend_used == "lexical_fallback"
    assert len(results) > 0
    assert any("500" in r.rule_number or "501" in r.rule_number for r in results)


def test_rag_backend_lexical_override(sample_vector_chunks):
    """Demuestra que si se fuerza RAG_BACKEND=lexical, se ignora pgvector aunque esté disponible."""
    mock_repo = MagicMock()
    mock_repo.is_available.return_value = True
    mock_embeddings = MagicMock()
    mock_embeddings.is_available.return_value = True

    rag_store = RulesRAGStore(
        repository=mock_repo,
        embedding_service=mock_embeddings,
        backend="lexical",
    )

    results = rag_store.retrieve_rules("Ninjutsu", top_k=3)

    assert rag_store.last_backend_used == "lexical_fallback"
    mock_embeddings.embed_query.assert_not_called()
    mock_repo.vector_search.assert_not_called()
    assert any("702.48" in r.rule_number for r in results)
