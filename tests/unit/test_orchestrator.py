import pytest
from src.orchestrator import MTGOrchestrator
from src.api.schemas import ResponseType
from src.tools.mtg_api import CardItem, MTGAPIError



def test_orchestrator_classify_intent():
    orch = MTGOrchestrator()
    assert orch.classify_intent("¿Cómo funciona el maná?") == ResponseType.RULES
    assert orch.classify_intent("¿Qué fases hay en un turno?") == ResponseType.RULES
    assert orch.classify_intent("Mi rapaz hizo daño primero y uso ninja") == ResponseType.RULES
    assert orch.classify_intent("Busco una carta blanca guerrero") == ResponseType.CARD_SEARCH
    assert orch.classify_intent("Quiero una carta de Han Solo, blanca-roja") == ResponseType.CUSTOM_CARD
    assert orch.classify_intent("Hola buenas tardes") == ResponseType.CONVERSATION


def test_orchestrator_combat_interaction_verdict():
    orch = MTGOrchestrator()
    query = "Mi rapaz del campo de batalla ha hecho daño con su daña primero, si lo cambio con mi ninja de horas tardías ¿Aplico el daño?"
    result = orch.handle_message("sess-test-combat", query)

    assert result.type == ResponseType.RULES
    assert "sí" in result.message.lower() or "si" in result.message.lower()
    refs = [s.reference for s in result.sources]
    assert "CR 702.48c" in refs
    assert "CR 702.7b" in refs


def test_orchestrator_canonical_filters():
    orch = MTGOrchestrator()
    # Spanish localized terms must map to canonical MTG values
    filters = orch._extract_search_filters("Busco una carta blanca guerrero coste inferior a dos", {})
    assert filters.get("color") == "W"
    assert filters.get("subtype") == "Warrior"
    assert filters.get("max_cmc") == 1
    assert filters.get("cmc") is None


def test_orchestrator_rules_two_unknown_cards_interaction():
    orch = MTGOrchestrator()
    # Evaluator example: Interaction between two cards not in the hardcoded trio
    query = "¿Qué ocurre entre Sheoldred, the Apocalypse y Notion Thief cuando robo una carta?"
    result = orch.handle_message("sess-two-cards", query)

    assert result.type == ResponseType.RULES
    # Must retrieve and attach both cards with full Oracle text
    card_names = [c.name for c in result.cards]
    assert "Sheoldred, the Apocalypse" in card_names
    assert "Notion Thief" in card_names
    
    # Must ground the reasoning and cite replacement/draw rules
    assert "notion thief" in result.message.lower() or "ladrón de nociones" in result.message.lower()
    citations = [s.reference for s in result.sources]
    assert any("614" in cit for cit in citations)


def test_orchestrator_rules_missing_card_honest_rejection():
    orch = MTGOrchestrator()
    # Evaluator example: Mega Dragon 9000 does not exist
    query = "¿Cómo interactúa Mega Dragon 9000 con Black Lotus?"
    result = orch.handle_message("sess-missing-card", query)

    assert result.type == ResponseType.RULES
    # Must NOT hallucinate or fake a card
    assert result.cards == []
    assert result.sources == []
    assert "No pude identificar una carta llamada 'Mega Dragon 9000'" in result.message
    assert "¿Puedes comprobar el nombre?" in result.message


def test_orchestrator_rules_lightning_bolt_ward():
    orch = MTGOrchestrator()
    query = "¿Qué pasa si uso Lightning Bolt sobre una criatura con Ward?"
    result = orch.handle_message("sess-bolt-ward", query)

    assert result.type == ResponseType.RULES
    # Card is resolved
    assert len(result.cards) >= 1
    assert result.cards[0].name == "Lightning Bolt"
    # Citations contain Ward rule CR 702.21
    citations = [s.reference for s in result.sources]
    assert any("702.21" in cit for cit in citations)


def test_orchestrator_search_with_mana_keyword(mock_mtg_tool):
    """Verifies that mentioning 'mana' in a search request does not trigger the rules intent."""
    orch = MTGOrchestrator()
    query = "Busco una carta de color blanco de coste inferior a dos de mana que sea guerrero"
    res = orch.handle_message("sess-search-mana", query)

    assert res.type == ResponseType.CARD_SEARCH
    assert res.active_filters.color == "W"
    assert res.active_filters.subtype == "Warrior"
    assert res.active_filters.max_cmc == 1


def test_orchestrator_search_with_plurals_and_word_cmc(mock_mtg_tool):
    """Verifies that plural colors ('rojas') and Spanish word numbers ('cinco') are parsed accurately."""
    orch = MTGOrchestrator()
    query = "Encuentra cartas de tipo dragón rojas que tengan coste exacto cinco"
    res = orch.handle_message("sess-search-plurals", query)

    assert res.type == ResponseType.CARD_SEARCH
    assert res.active_filters.color == "R"
    assert res.active_filters.subtype == "Dragon"
    assert res.active_filters.cmc == 5


def test_orchestrator_rules_card_with_newlines():
    """Verifies that card names spanning newlines/extra spaces are properly normalized."""
    orch = MTGOrchestrator()
    query = "¿Qué pasa si uso Lightning\n  Bolt sobre una criatura con Ward?"
    res = orch.handle_message("sess-newlines", query)

    assert res.type == ResponseType.RULES
    assert len(res.cards) == 1
    assert res.cards[0].name == "Lightning Bolt"


def test_orchestrator_custom_card_darth_vader():
    """Verifies that Darth Vader request generates a Dimir card in local fallback mode."""
    orch = MTGOrchestrator()
    query = "Créame una carta custom de Darth Vader negra y azul"
    res = orch.handle_message("sess-vader", query)

    assert res.type == ResponseType.CUSTOM_CARD
    assert len(res.cards) == 1
    assert "Darth Vader" in res.cards[0].name
    assert "{U}" in res.cards[0].mana_cost and "{B}" in res.cards[0].mana_cost


def test_general_question_about_game_is_answered():
    orch = MTGOrchestrator()
    result = orch.handle_message(
        "session-general",
        "¿De qué se trata este juego?"
    )

    assert result.type == ResponseType.CONVERSATION
    assert "juego de cartas" in result.message.lower()
    assert "maná" in result.message.lower() or "mana" in result.message.lower()

    # La respuesta anterior incorrecta no debe aparecer.
    assert not result.message.endswith("¿En qué puedo ayudarte?")


def test_general_question_overview_variations():
    orch = MTGOrchestrator()
    variations = [
        "¿Qué es Magic?",
        "¿En qué consiste MTG?",
        "¿Cómo se juega este juego?"
    ]
    for query in variations:
        result = orch.handle_message(f"session-{query[:10]}", query)
        assert result.type == ResponseType.CONVERSATION
        assert "juego de cartas" in result.message.lower()
        assert not result.message.endswith("¿En qué puedo ayudarte?")


def test_general_greeting_returns_welcome():
    orch = MTGOrchestrator()
    result = orch.handle_message("session-greeting", "Hola")

    assert result.type == ResponseType.CONVERSATION
    assert "¡hola!" in result.message.lower()
    assert "asistente" in result.message.lower()
    # Menú completo hardcodeado de 4 puntos ya no debe aparecer
    assert "1. **reglas del juego**" not in result.message.lower()


def test_general_question_delegates_to_llm(monkeypatch):
    orch = MTGOrchestrator()
    captured_messages = []

    def mock_generate_text(messages, deployment=None, timeout=10.0):
        captured_messages.extend(messages)
        return "Magic fue creado por Richard Garfield en 1993."

    monkeypatch.setattr(orch.llm, "generate_text", mock_generate_text)
    result = orch.handle_message("session-llm", "¿Quién creó Magic y en qué año?")

    assert result.type == ResponseType.CONVERSATION
    assert "Richard Garfield" in result.message
    # Check that system prompt follows required constraints
    sys_content = next(m["content"] for m in captured_messages if m["role"] == "system")
    assert "responder directamente" in sys_content.lower()
    assert "no inventar texto oracle" in sys_content.lower()
    assert "comprehensive rules" in sys_content.lower()


def test_orchestrator_card_search_white_warrior_success(monkeypatch):
    """
    Verifies that 'Busco un guerrero blanco de coste uno' with a successful provider
    returns CARD_SEARCH, active filters, cards, and 1 external_api source.
    """
    orch = MTGOrchestrator()
    fake_cards = [
        CardItem(
            name="Dragon Hunter",
            mana_cost="{W}",
            cmc=1.0,
            type_line="Creature — Human Warrior",
            oracle_text="Protection from Dragons",
            image_url="http://gatherer.wizards.com/Handlers/Image.ashx?multiverseid=394541&type=card"
        ),
        CardItem(
            name="Aven Skirmisher",
            mana_cost="{W}",
            cmc=1.0,
            type_line="Creature — Bird Warrior",
            oracle_text="Flying",
            image_url="http://gatherer.wizards.com/Handlers/Image.ashx?multiverseid=391797&type=card"
        )
    ]

    def fake_search(*args, **kwargs):
        return fake_cards

    monkeypatch.setattr(orch.api_tool, "search_cards", fake_search)

    result = orch.handle_message("sess-success-ww1", "Busco un guerrero blanco de coste uno")

    assert result.type == ResponseType.CARD_SEARCH
    assert result.active_filters.color == "W"
    assert result.active_filters.subtype == "Warrior"
    assert result.active_filters.cmc == 1
    assert len(result.cards) == 2
    assert "He encontrado" in result.message
    assert len(result.sources) == 1
    assert result.sources[0].reference == "cards"


def test_orchestrator_card_search_provider_error_handling(monkeypatch):
    """
    Verifies that when the provider raises MTGAPIError, the orchestrator:
    - returns type CARD_SEARCH
    - preserves active_filters
    - returns cards = []
    - returns sources = [] (does NOT attribute source on failure)
    - responds explaining provider unavailability
    - does NOT say 'No he encontrado cartas en la base de datos'
    """
    orch = MTGOrchestrator()

    def fake_search_error(*args, **kwargs):
        raise MTGAPIError("MTG API connection failure", status_code=503)

    monkeypatch.setattr(orch.api_tool, "search_cards", fake_search_error)

    result = orch.handle_message("sess-err-ww1", "Busco un guerrero blanco de coste uno")

    assert result.type == ResponseType.CARD_SEARCH
    assert result.active_filters.color == "W"
    assert result.active_filters.subtype == "Warrior"
    assert result.active_filters.cmc == 1
    assert result.cards == []
    assert result.sources == []
    assert "No pude consultar el catálogo" in result.message
    assert "No he encontrado cartas" not in result.message


def test_orchestrator_card_search_empty_valid_response(monkeypatch):
    """
    Verifies that when the provider returns HTTP 200 with 0 results:
    - returns type CARD_SEARCH
    - preserves active_filters
    - returns cards = []
    - includes sources = 1 (valid evidence that catalog was queried)
    - informs user that no cards matched
    """
    orch = MTGOrchestrator()

    def fake_search_empty(*args, **kwargs):
        return []

    monkeypatch.setattr(orch.api_tool, "search_cards", fake_search_empty)

    result = orch.handle_message("sess-empty-ww1", "Busco un guerrero blanco de coste uno")

    assert result.type == ResponseType.CARD_SEARCH
    assert result.active_filters.color == "W"
    assert result.active_filters.subtype == "Warrior"
    assert result.active_filters.cmc == 1
    assert result.cards == []
    assert len(result.sources) == 1
    assert "No he encontrado cartas en la base de datos de MTG" in result.message
    assert "No pude consultar" not in result.message




