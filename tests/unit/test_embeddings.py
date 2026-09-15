import pytest
from unittest.mock import MagicMock
from src.services.embeddings import EmbeddingService
from src.config import settings


def test_embedding_dimension_is_1536():
    """Demuestra compatibilidad entre la configuración de embeddings y el esquema PostgreSQL vector(1536)."""
    service = EmbeddingService()
    assert service.dimensions == 1536
    assert service.deployment == "text-embedding-3-small"


def test_embedding_service_unavailable_without_credentials():
    """Demuestra que EmbeddingService reporta disponibilidad False si no hay credenciales."""
    service = EmbeddingService(api_key="", endpoint="")
    assert service.is_available() is False


def test_embed_query_when_unavailable_raises_runtime_error():
    """Demuestra que llamar a embed_query sin credenciales levanta RuntimeError informativo."""
    service = EmbeddingService(api_key="", endpoint="")
    with pytest.raises(RuntimeError, match="unavailable"):
        service.embed_query("¿Cómo funciona el maná?")


def test_embed_query_empty_string_raises_value_error():
    """Demuestra validación de entrada para queries vacías."""
    mock_client = MagicMock()
    service = EmbeddingService(api_key="sk-fake", client=mock_client)
    with pytest.raises(ValueError, match="empty"):
        service.embed_query("   ")


def test_embed_query_mock():
    """Demuestra que embed_query invoca correctamente el deployment y retorna lista de floats."""
    mock_client = MagicMock()
    mock_data = MagicMock()
    mock_data.embedding = [0.05] * 1536
    mock_response = MagicMock()
    mock_response.data = [mock_data]
    mock_client.embeddings.create.return_value = mock_response

    service = EmbeddingService(
        api_key="sk-fake",
        deployment="text-embedding-3-small",
        client=mock_client,
    )

    vector = service.embed_query("Fases del turno")

    assert len(vector) == 1536
    assert vector[0] == 0.05
    mock_client.embeddings.create.assert_called_once_with(
        input="Fases del turno",
        model="text-embedding-3-small",
    )


def test_embed_documents_batching():
    """Demuestra que embed_documents agrupa documentos en lotes para minimizar llamadas HTTP."""
    mock_client = MagicMock()

    def mock_create(input, model):
        res = MagicMock()
        items = []
        for idx, text in enumerate(input):
            item = MagicMock()
            item.index = idx
            item.embedding = [float(idx)] * 1536
            items.append(item)
        res.data = items
        return res

    mock_client.embeddings.create.side_effect = mock_create

    service = EmbeddingService(
        api_key="sk-fake",
        deployment="text-embedding-3-small",
        client=mock_client,
    )

    # 120 chunks con batch_size=50 -> 3 llamadas a embeddings.create (50, 50, 20)
    texts = [f"Rule chunk {i}" for i in range(120)]
    vectors = service.embed_documents(texts, batch_size=50)

    assert len(vectors) == 120
    assert mock_client.embeddings.create.call_count == 3
