import pytest
from unittest.mock import MagicMock
from src.agents.rules_reasoning_agent import RulesReasoningAgent, RulesReasoningOutput
from src.services.llm import LLMService
from src.services.rules_rag import RuleChunk


def test_rules_agent_deterministic_combat_interaction():
    agent = RulesReasoningAgent(llm_service=LLMService(api_key=""))
    
    query = "¿Si mi Rapaz del campo de batalla hizo daño primero y lo cambio con Ninja de horas tardías, aplica daño?"
    reply, sources = agent.run(query)

    # Verdict must be affirmative
    assert "sí" in reply.lower()
    assert "ninja de horas tardías" in reply.lower()
    
    # Must contain structured CR citations
    source_refs = [s.reference for s in sources]
    assert "CR 702.48c" in source_refs
    assert "CR 702.7b" in source_refs
    assert "CR 510.4" in source_refs


def test_rules_agent_deterministic_turn_phases():
    agent = RulesReasoningAgent(llm_service=LLMService(api_key=""))
    reply, sources = agent.run("¿Cuáles son las fases de un turno?")

    assert "Fase Inicial" in reply
    assert "Fase de Combate" in reply
    assert any("CR 500.1" in s.reference for s in sources)


def test_rules_agent_deterministic_mana():
    agent = RulesReasoningAgent(llm_service=LLMService(api_key=""))
    reply, sources = agent.run("¿Cómo funciona el maná en MTG?")

    assert "CR 106.1" in reply or any("CR 106.1" in s.reference for s in sources)


def test_rules_agent_rag_chunks_fallback():
    agent = RulesReasoningAgent(llm_service=LLMService(api_key=""))
    chunks = [
        RuleChunk(
            rule_id="CR-704.5",
            rule_number="704.5",
            category="State-Based Actions",
            title="State-Based Actions",
            content="If a player has 0 or less life, that player loses the game.",
            citation="CR 704.5"
        )
    ]
    reply, sources = agent.run("Consulta rara sobre SBA", rule_chunks=chunks)

    assert "704.5" in reply
    assert len(sources) == 1
    assert sources[0].reference == "CR 704.5"


def test_rules_agent_llm_structured_output_mock():
    mock_llm = MagicMock()
    mock_llm.is_available.return_value = True
    
    expected_output = RulesReasoningOutput(
        reasoning_steps=[
            "Paso 1: Criatura atacante bloqueada por dos criaturas.",
            "Paso 2: Asignación de daño de arrollar.",
            "Paso 3: Aplicación de regla CR 702.19b.",
            "Paso 4: Daño sobrante asignado al jugador defensor."
        ],
        verdict="El daño sobrante de arrollar sí pasa al jugador.",
        citations=["CR 702.19b"]
    )
    mock_llm.generate_structured.return_value = expected_output

    agent = RulesReasoningAgent(llm_service=mock_llm)
    reply, sources = agent.run("¿Cómo funciona arrollar con múltiples bloqueadores?")

    assert "El daño sobrante de arrollar sí pasa al jugador." in reply
    assert "CR 702.19b" in reply
    assert len(sources) == 1
    assert sources[0].reference == "CR 702.19b"


def test_rules_agent_ward_interaction():
    agent = RulesReasoningAgent(llm_service=LLMService(api_key=""))
    reply, sources = agent.run("¿Qué pasa si uso Lightning Bolt sobre una criatura con Ward?")

    assert "guardia" in reply.lower() or "ward" in reply.lower()
    assert "contrarresta" in reply.lower() or "contrarrestado" in reply.lower()
    source_refs = [s.reference for s in sources]
    assert any("702.21" in ref for ref in source_refs)


def test_rules_agent_sheoldred_notion_thief_interaction():
    agent = RulesReasoningAgent(llm_service=LLMService(api_key=""))
    reply, sources = agent.run("¿Qué ocurre entre Sheoldred, the Apocalypse y Notion Thief cuando un oponente roba?")

    assert "notion thief" in reply.lower() or "ladrón de nociones" in reply.lower()
    assert "sheoldred" in reply.lower()
    assert "reemplazo" in reply.lower() or "reemplazado" in reply.lower()
    source_refs = [s.reference for s in sources]
    assert any("614" in ref for ref in source_refs)

