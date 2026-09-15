from unittest.mock import MagicMock
from src.api.schemas import CardResult, ResponseType
from src.agents.custom_card_agent import CustomCardAgent, CustomCardOutput
from src.services.llm import LLMService
from src.orchestrator import MTGOrchestrator


def test_custom_card_agent_deterministic_han_solo():
    """
    Test D: Fallback Han Solo is completely in Spanish, has honest image_url=None,
    and extended CardResult fields.
    """
    agent = CustomCardAgent(llm_service=LLMService(api_key=""))
    reply, card = agent.run("Quiero una carta de Han Solo, blanca-roja con dañar primero", locale="es")

    # Spanish card attributes
    assert card.name == "Han Solo, Capitán del Halcón"
    assert card.mana_cost == "{1}{R}{W}"
    assert card.cmc == 3.0
    assert card.type_line == "Criatura legendaria — Humano Bribón Piloto"
    assert "Dañar primero" in card.oracle_text
    assert card.power == "3"
    assert card.toughness == "2"
    assert card.flavor_text == "Nunca me digas las probabilidades."
    assert card.is_custom is True
    assert card.image_url is None  # Test E: Honest image_url handling

    # Reply checks: concise introduction without duplicating card fields
    assert "Han Solo, Capitán del Halcón" in reply
    assert "{1}{R}{W}" not in reply
    assert "Criatura legendaria — Humano Bribón Piloto" not in reply
    assert "Dañar primero" not in reply
    assert "3/2" not in reply
    assert "Nunca me digas las probabilidades" not in reply

    # Test B: Verify reply does NOT leak internal prompts or AI providers
    assert "Prompt de Ilustración" not in reply
    assert "DALL-E" not in reply
    assert "Midjourney" not in reply
    assert "art_prompt" not in reply


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
        color_pie_rationale="El blanco domina la preservación de criaturas y justicia divina.",
        art_prompt="Gandalf standing atop a precipice in radiant white robes."
    )
    mock_llm.generate_structured.return_value = expected

    agent = CustomCardAgent(llm_service=mock_llm)
    reply, card = agent.run("Crea a Gandalf el Blanco", locale="es")

    assert card.name == "Gandalf el Blanco"
    assert card.cmc == 5.0
    assert card.image_url is None
    assert card.is_custom is True
    assert card.power == "4"
    assert card.toughness == "5"
    assert card.flavor_text == "Vuelvo a vosotros al cambiar la marea."
    assert "Gandalf el Blanco" in reply
    assert "4/5" not in reply
    assert "{3}{W}{W}" not in reply

    # Test B: Reply hygiene
    assert "Prompt de Ilustración" not in reply
    assert "DALL-E" not in reply
    assert "Midjourney" not in reply
    assert "art_prompt" not in reply


def test_custom_card_agent_prompt_locale_instruction():
    """
    Test A: Verify the prompt passed to the LLM contains unambiguous instruction
    to generate all visible fields in the requested locale (Spanish).
    """
    mock_llm = MagicMock()
    mock_llm.is_available.return_value = True
    mock_llm.generate_structured.return_value = CustomCardOutput(
        name="Prueba",
        mana_cost="{1}{U}",
        cmc=2.0,
        type_line="Instantáneo",
        oracle_text="Roba dos cartas.",
        color_pie_rationale="Azul roba cartas."
    )

    agent = CustomCardAgent(llm_service=mock_llm)
    agent.run("Hazme un hechizo de robo azul", locale="es")

    assert mock_llm.generate_structured.called
    call_kwargs = mock_llm.generate_structured.call_args.kwargs
    messages = call_kwargs["messages"]

    system_msg = next(m["content"] for m in messages if m["role"] == "system")
    user_msg = next(m["content"] for m in messages if m["role"] == "user")

    # Verify system prompt has strict Spanish localization rules
    assert "POLÍTICA ESTRICTA DE IDIOMA Y LOCALIZACIÓN" in system_msg
    assert "Dañar primero" in system_msg
    assert "español" in system_msg
    assert "locale" in system_msg

    # Verify user message specifies locale
    assert "Locale solicitado: 'es'" in user_msg


def test_custom_card_agent_internal_art_prompt_not_leaked():
    """
    Test C: Verify that art_prompt can exist internally in CustomCardOutput
    without being leaked to the public response.
    """
    mock_llm = MagicMock()
    mock_llm.is_available.return_value = True

    internal_art = "A cinematic digital painting of a Jedi knight with blue lightsaber in heavy rain."
    output_with_art = CustomCardOutput(
        name="Obi-Wan Kenobi",
        mana_cost="{2}{W}{U}",
        cmc=4.0,
        type_line="Criatura legendaria — Humano Caballero Jedi",
        power="3",
        toughness="4",
        oracle_text="Vigilancia. Siempre que bloquee, previene todo el daño que fuera a recibir este turno.",
        flavor_text="Hola a todos.",
        color_pie_rationale="Blanco y azul representan paciencia, defensa y serenidad táctica.",
        art_prompt=internal_art
    )
    mock_llm.generate_structured.return_value = output_with_art

    agent = CustomCardAgent(llm_service=mock_llm)
    reply, card = agent.run("Crea a Obi-Wan Kenobi", locale="es")

    # art_prompt is NOT in reply
    assert internal_art not in reply
    assert "Prompt de Ilustración" not in reply
    assert "DALL-E" not in reply
    assert "Midjourney" not in reply
    assert "art_prompt" not in reply

    # CardResult does not have art_prompt and image_url is strictly None
    assert not hasattr(card, "art_prompt")
    assert card.image_url is None
    assert card.is_custom is True


def test_custom_card_schema_extension():
    """
    Test F: Verify CardResult schema extension with power, toughness,
    flavor_text, and is_custom (with backwards compatibility).
    """
    # Custom card with extended fields
    custom_card = CardResult(
        name="Carta Custom",
        mana_cost="{R}",
        cmc=1.0,
        type_line="Criatura — Trasgo",
        oracle_text="Prisa.",
        power="2",
        toughness="1",
        flavor_text="¡Por la tribu!",
        is_custom=True
    )
    assert custom_card.power == "2"
    assert custom_card.toughness == "1"
    assert custom_card.flavor_text == "¡Por la tribu!"
    assert custom_card.is_custom is True
    assert custom_card.image_url is None

    # Standard card (backwards compatibility defaults)
    standard_card = CardResult(name="Lightning Bolt", cmc=1.0)
    assert standard_card.power is None
    assert standard_card.toughness is None
    assert standard_card.flavor_text is None
    assert standard_card.is_custom is False


def test_orchestrator_dependency_injection_custom_agents():
    mock_rules_agent = MagicMock()
    mock_rules_agent.run.return_value = ("Regla simulada", [])

    mock_card_agent = MagicMock()
    mock_card_result = CardResult(name="Carta simulada", cmc=2.0, is_custom=True)
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
    assert res_custom.cards[0].is_custom is True


def test_custom_card_reply_does_not_duplicate_card_content():
    """
    Verifies that CardResult is the single source of truth for custom card details,
    and that the assistant's reply does not duplicate mana_cost, type_line, oracle_text,
    power/toughness, or flavor_text.
    """
    agent = CustomCardAgent(llm_service=LLMService(api_key=""))
    output = CustomCardOutput(
        name="Erudito de las Mareas",
        mana_cost="{3}{U}{U}",
        cmc=5.0,
        type_line="Criatura — Humano Mago",
        oracle_text="Cuando entre al campo de batalla, roba una carta.",
        power="3",
        toughness="4",
        flavor_text="El flujo y reflujo de las mareas obedece al conocimiento.",
        color_pie_rationale="Azul representa conocimiento y ventaja de cartas.",
        art_prompt="A wise blue mage by the ocean shore."
    )
    reply, card = agent._format_response(output)

    # CardResult holds all details (single source of truth for the UI)
    assert card.name == "Erudito de las Mareas"
    assert card.mana_cost == "{3}{U}{U}"
    assert card.type_line == "Criatura — Humano Mago"
    assert card.oracle_text == "Cuando entre al campo de batalla, roba una carta."
    assert card.power == "3"
    assert card.toughness == "4"
    assert card.flavor_text == "El flujo y reflujo de las mareas obedece al conocimiento."
    assert card.is_custom is True
    assert card.image_url is None

    # Reply is a concise introduction and does NOT duplicate card components
    assert "{3}{U}{U}" not in reply
    assert "Criatura — Humano Mago" not in reply
    assert "Cuando entre al campo de batalla" not in reply
    assert "3/4" not in reply
    assert "El flujo y reflujo" not in reply
    assert "Erudito de las Mareas" in reply

