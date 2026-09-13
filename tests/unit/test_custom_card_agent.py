from unittest.mock import MagicMock
from src.api.schemas import CardResult
from src.agents.custom_card_agent import CustomCardAgent, CustomCardOutput
from src.services.llm import LLMService
from src.orchestrator import MTGOrchestrator


def test_custom_card_agent_deterministic_han_solo():
    agent = CustomCardAgent(llm_service=LLMService(api_key=""))
    reply, card = agent.run("Quiero una carta de Han Solo, blanca-roja con dañar primero")

    assert "Han Solo" in card.name
    assert card.mana_cost == "{1}{R}{W}"
    assert card.cmc == 3.0
    assert card.image_url is None  # Honest image_url handling
    assert "Dañar primero" in card.oracle_text
    assert "Color Pie" in reply


def test_custom_card_agent_llm_structured_mock():
    mock_llm = MagicMock()
    mock_llm.is_available.return_value = True

    expected = CustomCardOutput(
        name="Gandalf el Blanco",
        mana_cost="{3}{W}{W}",
        cmc=5.0,
        type_line="Criatura legendaria — Mago Avatar",
        power="4",
        toughness="5",
        oracle_text="Destello. Siempre que otra criatura que controlas muera, regrésala al campo de batalla bajo tu control al inicio del próximo paso final.",
        flavor_text="Vuelvo a vosotros al cambiar la marea.",
        color_pie_rationale="El blanco domina la preservación de criaturas y justicia divina."
    )
    mock_llm.generate_structured.return_value = expected

    agent = CustomCardAgent(llm_service=mock_llm)
    reply, card = agent.run("Crea a Gandalf el Blanco")

    assert card.name == "Gandalf el Blanco"
    assert card.cmc == 5.0
    assert card.image_url is None
    assert "4/5" in reply
    assert "Gandalf el Blanco" in reply


def test_orchestrator_dependency_injection_custom_agents():
    mock_rules_agent = MagicMock()
    mock_rules_agent.run.return_value = ("Regla simulada", [])

    mock_card_agent = MagicMock()
    mock_card_result = CardResult(name="Carta simulada", cmc=2.0)
    mock_card_agent.run.return_value = ("Carta simulada", mock_card_result)

    orchestrator = MTGOrchestrator(
        rules_agent=mock_rules_agent,
        custom_card_agent=mock_card_agent
    )

    # Trigger rules flow
    res_rules = orchestrator.handle_message("session-test-1", "Duda sobre fases de turno")
    assert mock_rules_agent.run.called
    assert res_rules.message == "Regla simulada"

    # Trigger custom card flow
    res_custom = orchestrator.handle_message("session-test-2", "Crea una carta custom de prueba")
    assert mock_card_agent.run.called
    assert res_custom.message == "Carta simulada"
