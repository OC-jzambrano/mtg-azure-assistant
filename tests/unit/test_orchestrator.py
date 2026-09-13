import pytest
from src.orchestrator import MTGOrchestrator
from src.api.schemas import ResponseType


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

