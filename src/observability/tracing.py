import os
import re
import logging
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Generator, Set
from pydantic import BaseModel

from src.config import settings

logger = logging.getLogger("mtg_assistant.observability")

REDACTED_KEYS: Set[str] = {
    "reasoning_steps",
    "chain_of_thought",
    "cot",
    "thoughts",
    "internal_reasoning",
    "private_reasoning",
    "api_key",
    "authorization",
    "password",
    "secret",
    "token",
    "jwt",
    "database_url",
    "azure_openai_api_key",
    "openai_api_key",
    "langfuse_secret_key",
    "azure_credentials",
}


def sanitize_llm_output(data: Any) -> Any:
    """
    Sanitizes LLM outputs and observation payloads before sending to Langfuse.
    Recursively redacts private reasoning (reasoning_steps, CoT) and secrets/tokens.
    """
    if data is None:
        return None

    if isinstance(data, BaseModel):
        data = data.model_dump()

    if isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            k_clean = str(k).lower().strip()
            if k_clean in REDACTED_KEYS or any(secret_term in k_clean for secret_term in ["api_key", "secret_key", "password"]):
                continue
            sanitized[k] = sanitize_llm_output(v)
        return sanitized

    if isinstance(data, list):
        return [sanitize_llm_output(item) for item in data]

    if isinstance(data, tuple):
        return tuple(sanitize_llm_output(item) for item in data)

    if isinstance(data, str):
        # Redact potential API keys or authorization bearer tokens
        if data.startswith("sk-") or "Bearer " in data:
            return "[REDACTED_SECRET]"
        return data

    return data


class NoOpObservation:
    """Null Object pattern for traces and observations when Langfuse is disabled or offline."""

    def __init__(self, name: str = "", as_type: str = "span", **kwargs):
        self.name = name
        self.as_type = as_type
        self.id = "noop"
        self.trace_id = "noop"
        self.attributes = kwargs

    def update(self, **kwargs) -> "NoOpObservation":
        self.attributes.update(kwargs)
        return self

    def end(self, **kwargs) -> None:
        pass


class TracingService:
    """
    Encapsulates Langfuse v4 AI Observability.
    Provides no-op execution when disabled, credentials missing, or offline.
    Propagates session_id (= conversation_id) across all child observations.
    """

    def __init__(self, client: Optional[Any] = None):
        self._custom_client = client
        self._client: Optional[Any] = client
        self._client_initialized: bool = client is not None

    @property
    def is_enabled(self) -> bool:
        if self._custom_client is not None:
            return True
        return bool(
            settings.langfuse_enabled
            and settings.langfuse_public_key
            and settings.langfuse_secret_key
        )

    def set_client(self, client: Any) -> None:
        """Allows injecting a mock or custom Langfuse client for testing."""
        self._custom_client = client
        self._client = client
        self._client_initialized = True

    def reset_client(self) -> None:
        """Resets client to configuration defaults."""
        self._custom_client = None
        self._client = None
        self._client_initialized = False

    def _get_client(self) -> Optional[Any]:
        if self._client_initialized:
            return self._client

        self._client_initialized = True
        if not self.is_enabled:
            return None

        try:
            from langfuse import Langfuse

            self._client = Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                base_url=settings.langfuse_base_url,
                environment=settings.app_environment,
                release=settings.version,
                tracing_enabled=True,
            )
            return self._client
        except Exception as exc:
            logger.warning(
                "Failed to initialize Langfuse client. Falling back to no-op. Error: %s",
                str(exc)
            )
            self._client = None
            return None

    @contextmanager
    def chat_trace(
        self,
        conversation_id: str,
        message: str
    ) -> Generator[Any, None, None]:
        """
        Root trace for a single turn of /api/chat.
        Groups all child observations under session_id = conversation_id.
        """
        # Determine root input depending on content capture setting
        if settings.langfuse_capture_content:
            initial_input = {"message": message}
        else:
            initial_input = {"message_length": len(message)}

        initial_metadata = {"session_id": conversation_id}

        client = self._get_client()
        if client is None:
            yield NoOpObservation(name="chat_turn", as_type="span", input=initial_input, metadata=initial_metadata)
            return

        try:
            from langfuse import propagate_attributes
            root_cm = client.start_as_current_observation(
                name="chat_turn",
                as_type="span",
                input=initial_input,
                metadata=initial_metadata
            )
        except Exception as exc:
            logger.warning("Error initializing Langfuse chat_trace: %s", str(exc))
            yield NoOpObservation(name="chat_turn", as_type="span", input=initial_input, metadata=initial_metadata)
            return

        with root_cm as root_obs:
            with propagate_attributes(
                session_id=conversation_id,
                environment=settings.app_environment,
                version=settings.version,
                tags=["mtg-assistant", "chat"],
                trace_name="chat_turn"
            ):
                try:
                    yield root_obs
                except Exception as exc:
                    root_obs.update(
                        level="ERROR",
                        status_message=type(exc).__name__
                    )
                    raise

    @contextmanager
    def observation(
        self,
        name: str,
        as_type: str = "span",
        input: Optional[Any] = None,
        output: Optional[Any] = None,
        metadata: Optional[Any] = None,
        level: Optional[str] = None,
        status_message: Optional[str] = None,
        model: Optional[str] = None,
        model_parameters: Optional[Dict[str, Any]] = None,
        usage_details: Optional[Dict[str, int]] = None,
        cost_details: Optional[Dict[str, float]] = None,
        version: Optional[str] = None
    ) -> Generator[Any, None, None]:
        """
        Creates a typed child observation (span, agent, tool, retriever, generation, embedding).
        Automatically nests inside the active OpenTelemetry context.
        """
        client = self._get_client()
        if client is None:
            yield NoOpObservation(
                name=name,
                as_type=as_type,
                input=input,
                output=output,
                metadata=metadata,
                model=model,
                usage_details=usage_details
            )
            return

        sanitized_input = sanitize_llm_output(input) if input is not None else None
        sanitized_output = sanitize_llm_output(output) if output is not None else None
        sanitized_metadata = sanitize_llm_output(metadata) if metadata is not None else None

        obs_kwargs: Dict[str, Any] = {
            "name": name,
            "as_type": as_type,
        }
        if sanitized_input is not None:
            obs_kwargs["input"] = sanitized_input
        if sanitized_output is not None:
            obs_kwargs["output"] = sanitized_output
        if sanitized_metadata is not None:
            obs_kwargs["metadata"] = sanitized_metadata
        if level is not None:
            obs_kwargs["level"] = level
        if status_message is not None:
            obs_kwargs["status_message"] = status_message
        if model is not None:
            obs_kwargs["model"] = model
        if model_parameters is not None:
            obs_kwargs["model_parameters"] = model_parameters
        if usage_details is not None:
            obs_kwargs["usage_details"] = usage_details
        if cost_details is not None:
            obs_kwargs["cost_details"] = cost_details
        if version is not None:
            obs_kwargs["version"] = version

        try:
            obs_cm = client.start_as_current_observation(**obs_kwargs)
        except Exception as exc:
            logger.warning("Error creating Langfuse observation '%s': %s", name, str(exc))
            yield NoOpObservation(**obs_kwargs)
            return

        with obs_cm as obs:
            try:
                yield obs
            except Exception as exc:
                obs.update(
                    level="ERROR",
                    status_message=type(exc).__name__
                )
                raise

    def build_root_output(self, result: Any, fallback_used: bool = False) -> Dict[str, Any]:
        """Formats the root trace output payload respecting content capture settings."""
        resp_type = result.type.value if hasattr(result.type, "value") else str(result.type)

        if settings.langfuse_capture_content:
            return {
                "type": resp_type,
                "message": result.message,
                "cards": [c.name for c in result.cards],
                "sources": [s.reference for s in result.sources],
                "fallback_used": fallback_used
            }
        else:
            return {
                "type": resp_type,
                "cards_count": len(result.cards),
                "sources_count": len(result.sources),
                "fallback_used": fallback_used
            }

    def flush(self) -> None:
        """Flushes pending events to Langfuse."""
        client = self._get_client()
        if client and hasattr(client, "flush"):
            try:
                client.flush()
            except Exception as exc:
                logger.warning("Failed to flush Langfuse events: %s", str(exc))

    def shutdown(self) -> None:
        """Flushes and shuts down the Langfuse client on application termination."""
        client = self._get_client()
        if client and hasattr(client, "shutdown"):
            try:
                client.shutdown()
            except Exception as exc:
                logger.warning("Failed to shut down Langfuse client: %s", str(exc))


# Global singleton instance
tracing = TracingService()
