import logging
from typing import List, Optional, Any
from src.config import settings
from src.observability.tracing import tracing

logger = logging.getLogger("mtg_assistant.embeddings")


class EmbeddingService:
    """
    Dedicated Embedding Service for generating vector embeddings via Azure OpenAI or OpenAI.
    Separated from LLM completion services to preserve single responsibility.
    """

    def __init__(
        self,
        endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        deployment: Optional[str] = None,
        dimensions: Optional[int] = None,
        client: Optional[Any] = None,
    ):
        self.endpoint = endpoint or settings.azure_openai_endpoint
        self.api_key = api_key or settings.azure_openai_api_key or settings.openai_api_key
        self.deployment = deployment or settings.azure_openai_embedding_deployment
        self.dimensions = dimensions or settings.embedding_dimensions

        self._client = client
        self._client_initialized = client is not None

    def _get_client(self) -> Optional[Any]:
        if self._client_initialized:
            return self._client

        self._client_initialized = True
        if not self.api_key:
            logger.info("No embedding API key configured. Vector embeddings unavailable.")
            return None

        try:
            from openai import AzureOpenAI, OpenAI

            if self.endpoint:
                self._client = AzureOpenAI(
                    azure_endpoint=self.endpoint,
                    api_key=self.api_key,
                    api_version="2024-06-01",
                    timeout=15.0,
                )
            else:
                self._client = OpenAI(
                    api_key=self.api_key,
                    timeout=15.0,
                )
            return self._client
        except Exception as exc:
            logger.warning("Failed to initialize embedding client: %s", exc)
            self._client = None
            return None

    def is_available(self) -> bool:
        """Returns True if the embedding client is initialized and credentials are provided."""
        return self._get_client() is not None

    def embed_query(self, text: str) -> List[float]:
        """
        Generates a vector embedding for a single search query text.
        Returns a list of 1536 floats.
        Raises RuntimeError if client is unavailable or API call fails.
        """
        client = self._get_client()
        if client is None:
            raise RuntimeError("EmbeddingService is unavailable: no client or API key configured.")

        clean_text = text.strip()
        if not clean_text:
            raise ValueError("Query text for embedding cannot be empty.")

        with tracing.observation(
            name="embed_query",
            as_type="span",
            metadata={
                "provider": "azure_openai" if self.endpoint else "openai",
                "deployment": self.deployment,
                "dimensions": self.dimensions,
            },
        ) as obs:
            try:
                response = client.embeddings.create(
                    input=clean_text,
                    model=self.deployment,
                )
                embedding = response.data[0].embedding
                obs.update(output={"dimensions": len(embedding)})
                return embedding
            except Exception as exc:
                obs.update(level="ERROR", status_message=type(exc).__name__)
                logger.warning("Failed to generate query embedding: %s", exc)
                raise RuntimeError(f"Embedding generation failed: {exc}") from exc

    def embed_documents(self, texts: List[str], batch_size: int = 50) -> List[List[float]]:
        """
        Generates vector embeddings for a list of document chunks using batching.
        Batches requests (default 50 chunks per batch) to minimize HTTP round-trips.
        Raises RuntimeError if client is unavailable or API call fails.
        """
        client = self._get_client()
        if client is None:
            raise RuntimeError("EmbeddingService is unavailable: no client or API key configured.")

        if not texts:
            return []

        all_embeddings: List[List[float]] = []

        with tracing.observation(
            name="embed_documents_batch",
            as_type="span",
            metadata={
                "provider": "azure_openai" if self.endpoint else "openai",
                "deployment": self.deployment,
                "total_documents": len(texts),
                "batch_size": batch_size,
            },
        ) as obs:
            try:
                for i in range(0, len(texts), batch_size):
                    batch = texts[i : i + batch_size]
                    response = client.embeddings.create(
                        input=batch,
                        model=self.deployment,
                    )
                    # Embeddings in response.data are ordered by index
                    sorted_data = sorted(response.data, key=lambda item: getattr(item, "index", 0))
                    for item in sorted_data:
                        all_embeddings.append(item.embedding)

                obs.update(output={"embedded_count": len(all_embeddings)})
                return all_embeddings
            except Exception as exc:
                obs.update(level="ERROR", status_message=type(exc).__name__)
                logger.warning("Failed to generate document embeddings in batch: %s", exc)
                raise RuntimeError(f"Batch embedding generation failed: {exc}") from exc


# Default global instance
embedding_service = EmbeddingService()
