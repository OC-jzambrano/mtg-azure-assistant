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
