import pytest
from unittest.mock import MagicMock, patch
from contextlib import contextmanager
from typing import List, Dict, Any

from src.observability.tracing import tracing
from src.orchestrator import MTGOrchestrator
from src.agents.rules_reasoning_agent import RulesReasoningAgent, RulesReasoningOutput
from src.agents.custom_card_agent import CustomCardAgent, CustomCardOutput
from src.services.llm import LLMService
from src.services.rules_rag import RuleChunk
from src.api.schemas import CardResult


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
def mock_pipeline_tracing():
    client = MockLangfuseClient()
    tracing.set_client(client)
    yield client
    tracing.reset_client()


def test_router_creates_observation(mock_pipeline_tracing):
    """Verify that MTGOrchestrator creates a route_intent span."""
    orchestrator = MTGOrchestrator()
    orchestrator.handle_message("conv-router-1", "¿Cómo funciona el maná?")

    names = [o.name for o in mock_pipeline_tracing.observations]
    assert "route_intent" in names

    route_obs = next(o for o in mock_pipeline_tracing.observations if o.name == "route_intent")
    assert route_obs.as_type == "span"
    assert route_obs.kwargs.get("metadata", {}).get("router_type") == "deterministic"
    assert any(u.get("output", {}).get("intent") == "rules" for u in route_obs.updates)


def test_card_search_creates_tool_observation(mock_pipeline_tracing):
    """Verify that card search flow produces extract_card_filters and mtg_card_search tool observation."""
    orchestrator = MTGOrchestrator()
    orchestrator.handle_message("conv-search-1", "Busco una carta blanca guerrero de coste inferior a dos")

    names = [o.name for o in mock_pipeline_tracing.observations]
    assert "extract_card_filters" in names
    assert "mtg_card_search" in names

    search_obs = next(o for o in mock_pipeline_tracing.observations if o.name == "mtg_card_search")
    assert search_obs.as_type == "tool"
    assert search_obs.kwargs.get("metadata", {}).get("color") == "W"
    assert search_obs.kwargs.get("metadata", {}).get("subtype") == "Warrior"
    assert any("results_count" in u.get("output", {}) for u in search_obs.updates)


def test_rule_retrieval_creates_retriever_observation(mock_pipeline_tracing):
    """Verify that rule retrieval produces a retriever observation with retrieval_backend=lexical_fallback."""
    orchestrator = MTGOrchestrator()
    orchestrator.handle_message("conv-rules-1", "Dime las fases del turno")

    names = [o.name for o in mock_pipeline_tracing.observations]
    assert "retrieve_rules" in names

    ret_obs = next(o for o in mock_pipeline_tracing.observations if o.name == "retrieve_rules")
    assert ret_obs.as_type == "retriever"
    # DoD check: backend must be labeled as lexical_fallback until pgvector slice
    assert ret_obs.kwargs.get("metadata", {}).get("retrieval_backend") == "lexical_fallback"
    assert any("rules" in u.get("output", {}) for u in ret_obs.updates)


def test_rules_agent_creates_agent_observation(mock_pipeline_tracing):
    """Verify that RulesReasoningAgent creates an agent observation without reasoning_steps."""
    agent = RulesReasoningAgent()
    chunks = [
        RuleChunk(
            rule_id="106_1",
            rule_number="106.1",
            category="General",
            title="Mana",
            content="Mana is the primary resource in the game.",
            citation="CR 106.1"
        )
    ]
    reply, sources = agent.run("¿Cómo funciona el maná?", rule_chunks=chunks, cards=[])

    names = [o.name for o in mock_pipeline_tracing.observations]
    assert "rules_reasoning_agent" in names
    assert "deterministic_fallback" in names

    agent_obs = next(o for o in mock_pipeline_tracing.observations if o.name == "rules_reasoning_agent")
    assert agent_obs.as_type == "agent"
    assert agent_obs.kwargs.get("metadata", {}).get("rules_count") == 1
    assert agent_obs.kwargs.get("metadata", {}).get("cards_count") == 0

    # Ensure no reasoning_steps in agent updates
    for u in agent_obs.updates:
        out = u.get("output", {})
        assert "reasoning_steps" not in out
        assert "citations" in out
        assert out.get("fallback_used") is True


def test_custom_card_agent_creates_agent_observation(mock_pipeline_tracing):
    """Verify that CustomCardAgent creates a custom_card_agent observation."""
    agent = CustomCardAgent()
    reply, card = agent.run("Crea una carta de Han Solo")

    names = [o.name for o in mock_pipeline_tracing.observations]
    assert "custom_card_agent" in names
    assert "deterministic_fallback" in names

    agent_obs = next(o for o in mock_pipeline_tracing.observations if o.name == "custom_card_agent")
    assert agent_obs.as_type == "agent"
    for u in agent_obs.updates:
        out = u.get("output", {})
        assert "card_name" in out
        assert "mana_cost" in out
        assert "cmc" in out
        assert out.get("fallback_used") is True


def test_llm_success_creates_generation(mock_pipeline_tracing):
    """Verify that successful LLM structured call produces generation with tokens and stripped CoT."""
    mock_choice = MagicMock()
    mock_choice.message.parsed = RulesReasoningOutput(
        reasoning_steps=["Paso interno privado que debe eliminarse"],
        verdict="El daño de combate sí se aplica.",
        citations=["CR 702.48c", "CR 510.4"]
    )

    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]
    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 120
    mock_usage.completion_tokens = 60
    mock_usage.total_tokens = 180
    mock_completion.usage = mock_usage

    mock_openai_client = MagicMock()
    mock_openai_client.beta.chat.completions.parse.return_value = mock_completion

    llm = LLMService(api_key="mock-key", client=mock_openai_client)
    res = llm.generate_structured(
        messages=[{"role": "user", "content": "test query"}],
        response_model=RulesReasoningOutput
    )

    assert res is not None
    names = [o.name for o in mock_pipeline_tracing.observations]
    assert "azure_openai_structured" in names

    gen_obs = next(o for o in mock_pipeline_tracing.observations if o.name == "azure_openai_structured")
    assert gen_obs.as_type == "generation"
    assert gen_obs.kwargs.get("model") == "gpt-4o"

    update_payload = gen_obs.updates[0]
    usage = update_payload.get("usage_details")
    assert usage is not None
    assert usage["prompt_tokens"] == 120
    assert usage["completion_tokens"] == 60
    assert usage["total_tokens"] == 180

    output = update_payload.get("output")
    assert output is not None
    assert "verdict" in output
    assert "citations" in output
    # STRICT CHECK: reasoning_steps MUST NOT be in generation output
    assert "reasoning_steps" not in output


def test_llm_error_records_fallback(mock_pipeline_tracing):
    """Verify that LLM failure records level=ERROR on generation and creates deterministic_fallback span."""
    mock_openai_client = MagicMock()
    mock_openai_client.beta.chat.completions.parse.side_effect = TimeoutError("Gateway timeout from Azure OpenAI")

    llm = LLMService(api_key="mock-key", client=mock_openai_client)
    agent = RulesReasoningAgent(llm_service=llm)

    reply, sources = agent.run("¿Cómo funcionan las fases del turno?")

    names = [o.name for o in mock_pipeline_tracing.observations]
    assert "azure_openai_structured" in names
    assert "deterministic_fallback" in names

    gen_obs = next(o for o in mock_pipeline_tracing.observations if o.name == "azure_openai_structured")
    assert any(u.get("level") == "ERROR" for u in gen_obs.updates)

    fallback_obs = next(o for o in mock_pipeline_tracing.observations if o.name == "deterministic_fallback")
    assert fallback_obs.as_type == "span"
    assert fallback_obs.kwargs.get("metadata", {}).get("agent") == "rules_reasoning"
    assert fallback_obs.kwargs.get("metadata", {}).get("reason") == "structured_output_error"
