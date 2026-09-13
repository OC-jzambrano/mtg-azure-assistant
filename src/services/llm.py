import os
import logging
from typing import Optional, Type, TypeVar, List, Dict, Any
from pydantic import BaseModel

from src.config import settings

logger = logging.getLogger("mtg_assistant.llm")

T = TypeVar("T", bound=BaseModel)


class LLMService:
    """
    Centralized LLM Service for Azure OpenAI and standard OpenAI.
    Supports Structured Outputs (Pydantic parsing) with automatic graceful fallback
    to local deterministic engines whenever credentials are missing, network fails, or timeout occurs.
    """

    def __init__(
        self,
        endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        deployment: Optional[str] = None,
        deployment_reasoning: Optional[str] = None,
        client: Optional[Any] = None
    ):
        self.endpoint = endpoint or settings.azure_openai_endpoint
        self.api_key = api_key or settings.azure_openai_api_key or settings.openai_api_key
        self.deployment = deployment or settings.azure_openai_deployment
        self.deployment_reasoning = deployment_reasoning or settings.azure_openai_deployment_reasoning
        
        self._client = client
        self._client_initialized = client is not None

    def _get_client(self) -> Optional[Any]:
        if self._client_initialized:
            return self._client

        self._client_initialized = True
        if not self.api_key:
            logger.info("No LLM API key configured. Deterministic local fallback is active.")
            return None

        try:
            from openai import AzureOpenAI, OpenAI

            if self.endpoint:
                self._client = AzureOpenAI(
                    azure_endpoint=self.endpoint,
                    api_key=self.api_key,
                    api_version="2024-06-01",
                    timeout=10.0
                )
            else:
                self._client = OpenAI(
                    api_key=self.api_key,
                    timeout=10.0
                )
            return self._client
        except Exception as exc:
            logger.warning(
                "Failed to initialize OpenAI/AzureOpenAI client; activating deterministic fallback. Error: %s",
                str(exc)
            )
            self._client = None
            return None

    def is_available(self) -> bool:
        return self._get_client() is not None

    def generate_structured(
        self,
        messages: List[Dict[str, str]],
        response_model: Type[T],
        deployment: Optional[str] = None,
        timeout: float = 10.0
    ) -> Optional[T]:
        """
        Executes a chat completion with Structured Outputs parsing into a Pydantic model.
        Returns None if client is unavailable, error occurs, or call times out.
        """
        client = self._get_client()
        if client is None:
            logger.warning(
                "LLM unavailable (no client configured). Falling back to deterministic reasoning."
            )
            return None

        model_name = deployment or self.deployment_reasoning

        try:
            completion = client.beta.chat.completions.parse(
                model=model_name,
                messages=messages,
                response_format=response_model,
                timeout=timeout
            )
            parsed = completion.choices[0].message.parsed
            return parsed
        except Exception as exc:
            logger.warning(
                "Azure OpenAI structured completion call failed. Activating deterministic fallback. Details: %s",
                str(exc),
                extra={"deployment": model_name, "error_type": type(exc).__name__}
            )
            return None

    def generate_text(
        self,
        messages: List[Dict[str, str]],
        deployment: Optional[str] = None,
        timeout: float = 10.0
    ) -> Optional[str]:
        """
        Executes standard chat completion and returns text, or None on failure.
        """
        client = self._get_client()
        if client is None:
            logger.warning(
                "LLM unavailable (no client configured). Falling back to deterministic generator."
            )
            return None

        model_name = deployment or self.deployment
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                timeout=timeout
            )
            return response.choices[0].message.content
        except Exception as exc:
            logger.warning(
                "Azure OpenAI text completion call failed. Activating deterministic fallback. Details: %s",
                str(exc),
                extra={"deployment": model_name, "error_type": type(exc).__name__}
            )
            return None
