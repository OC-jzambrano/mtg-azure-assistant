import pytest
from unittest.mock import patch, MagicMock
from contextlib import contextmanager
from typing import List, Dict, Any

from src.config import settings
from src.observability.tracing import (
    tracing,
    sanitize_llm_output,
    NoOpObservation,
    TracingService
)
from src.api.schemas import ResponseType, CardResult, SourceRef
from src.orchestrator import AssistantResult


class MockObs:
    def __init__(self, name: str, as_type: str = "span", **kwargs):
        self.name = name
        self.as_type = as_type
        self.kwargs = kwargs
        self.updates: List[Dict[str, Any]] = []
        self.id = f"mock-{name}"
        self.trace_id = "mock-trace-123"

    def update(self, **kwargs):
        self.updates.append(kwargs)
        return self

    def end(self, **kwargs):
        pass


class MockLangfuseClient:
    def __init__(self):
        self.observations: List[MockObs] = []
        self.flushed = False
        self.shutdown_called = False

    @contextmanager
    def start_as_current_observation(self, name: str, as_type: str = "span", **kwargs):
        obs = MockObs(name=name, as_type=as_type, **kwargs)
        self.observations.append(obs)
        yield obs

    def flush(self):
        self.flushed = True

    def shutdown(self):
        self.shutdown_called = True


@pytest.fixture
def mock_tracing():
    client = MockLangfuseClient()
    tracing.set_client(client)
    yield client
    tracing.reset_client()


def test_langfuse_disabled_is_noop():
    """Verify that when Langfuse is disabled, tracing is a pure no-op and raises no exceptions."""
    with patch.object(settings, "langfuse_enabled", False):
        service = TracingService()
        assert not service.is_enabled

        with service.chat_trace(conversation_id="conv-1", message="hello") as trace:
            assert isinstance(trace, NoOpObservation)
            trace.update(status="ok")
            assert trace.attributes.get("status") == "ok"

        with service.observation(name="tool_call", as_type="tool") as obs:
            assert isinstance(obs, NoOpObservation)
            assert obs.name == "tool_call"
            assert obs.as_type == "tool"
            obs.update(output={"result": 42})


def test_chat_trace_uses_conversation_id_as_session(mock_tracing):
    """Verify that chat_trace uses conversation_id as session_id and creates chat_turn root observation."""
    conv_id = "test-session-uuid-123"
    msg = "Explain mana pool"

    with patch("langfuse.propagate_attributes") as mock_propagate:
        mock_propagate.return_value.__enter__ = MagicMock()
        mock_propagate.return_value.__exit__ = MagicMock()

        with tracing.chat_trace(conversation_id=conv_id, message=msg) as trace:
            trace.update(output={"done": True})

        mock_propagate.assert_called_once()
        _, kwargs = mock_propagate.call_args
        assert kwargs["session_id"] == conv_id
        assert kwargs["trace_name"] == "chat_turn"
        assert "mtg-assistant" in kwargs["tags"]

    assert len(mock_tracing.observations) == 1
    root = mock_tracing.observations[0]
    assert root.name == "chat_turn"
    assert root.as_type == "span"
    assert root.kwargs.get("metadata", {}).get("session_id") == conv_id


def test_telemetry_does_not_contain_reasoning_steps():
    """Verify that sanitize_llm_output strips reasoning_steps, chain_of_thought, cot, etc."""
    payload = {
        "verdict": "El daño entra en combate.",
        "citations": ["CR 702.48c", "CR 510.4"],
        "reasoning_steps": [
            "Paso 1: Se asigna daño en el primer paso.",
            "Paso 2: Se activa ninjutsu.",
            "Paso 3: El ninja entra atacando y no ha hecho daño."
        ],
        "chain_of_thought": "Private internal thoughts of the LLM",
        "cot": "Another CoT abbreviation",
        "thoughts": "Model thoughts",
        "internal_reasoning": "Hidden chain",
        "nested": {
            "reasoning_steps": ["step A", "step B"],
            "safe_detail": "Valid data"
        }
    }

    sanitized = sanitize_llm_output(payload)
    assert "verdict" in sanitized
    assert "citations" in sanitized
    assert "reasoning_steps" not in sanitized
    assert "chain_of_thought" not in sanitized
    assert "cot" not in sanitized
    assert "thoughts" not in sanitized
    assert "internal_reasoning" not in sanitized
    assert "reasoning_steps" not in sanitized["nested"]
    assert sanitized["nested"]["safe_detail"] == "Valid data"


def test_telemetry_does_not_contain_api_keys():
    """Verify that sanitize_llm_output strips credentials, tokens, and API keys."""
    payload = {
        "action": "resolve",
        "api_key": "secret-api-key-12345",
        "openai_api_key": "sk-proj-supersecret12345",
        "authorization": "Bearer eyJhbGciOi...",
        "password": "my_password",
        "secret": "confidential",
        "database_url": "postgresql://user:pass@localhost:5432/db",
        "raw_text": "sk-realapikeyhere1234567890",
        "nested": {
            "token": "jwt-token-val",
            "safe_count": 5
        }
    }

    sanitized = sanitize_llm_output(payload)
    assert sanitized["action"] == "resolve"
    assert "api_key" not in sanitized
    assert "openai_api_key" not in sanitized
    assert "authorization" not in sanitized
    assert "password" not in sanitized
    assert "secret" not in sanitized
    assert "database_url" not in sanitized
    assert "token" not in sanitized["nested"]
    assert sanitized["nested"]["safe_count"] == 5
    assert sanitized["raw_text"] == "[REDACTED_SECRET]"


def test_content_capture_disabled_redacts_lengths_and_counts():
    """Verify conservative mode when LANGFUSE_CAPTURE_CONTENT=false."""
    fake_result = AssistantResult(
        type=ResponseType.RULES,
        message="Respuesta completa con reglas y detalles extensos de juego.",
        cards=[CardResult(name="Lightning Bolt")],
        sources=[SourceRef(kind="rule", title="Rules", reference="CR 702.21a")]
    )

    with patch.object(settings, "langfuse_capture_content", False):
        output = tracing.build_root_output(fake_result, fallback_used=False)
        assert "message" not in output
        assert "cards" not in output
        assert output["cards_count"] == 1
        assert output["sources_count"] == 1
        assert output["type"] == "rules"
        assert output["fallback_used"] is False


def test_content_capture_enabled_preserves_content():
    """Verify content capture when LANGFUSE_CAPTURE_CONTENT=true."""
    fake_result = AssistantResult(
        type=ResponseType.RULES,
        message="Respuesta completa.",
        cards=[CardResult(name="Lightning Bolt")],
        sources=[SourceRef(kind="rule", title="Rules", reference="CR 702.21a")]
    )

    with patch.object(settings, "langfuse_capture_content", True):
        output = tracing.build_root_output(fake_result, fallback_used=False)
        assert output["message"] == "Respuesta completa."
        assert output["cards"] == ["Lightning Bolt"]
        assert output["sources"] == ["CR 702.21a"]


def test_tracing_error_isolation():
    """Verify that errors inside Langfuse SDK never crash the application logic."""
    class FailingClient:
        def start_as_current_observation(self, *args, **kwargs):
            raise RuntimeError("Langfuse server connection failed")

    broken_service = TracingService(client=FailingClient())
    with broken_service.chat_trace(conversation_id="conv-err", message="test") as trace:
        assert isinstance(trace, NoOpObservation)

    with broken_service.observation(name="test_obs") as obs:
        assert isinstance(obs, NoOpObservation)
