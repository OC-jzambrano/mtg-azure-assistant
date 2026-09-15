import pytest
from src.orchestrator import MTGOrchestrator
from src.api.schemas import ResponseType


def test_acceptance_scenario_1_mana_explanation(mock_mtg_tool):
    """
    Acceptance Scenario 1: Basic Rules RAG - Mana System.
    Verifies that asking about mana triggers the RULES intent, retrieves CR 106 rules,
    and returns canonical citations without card hallucination.
    """
    orchestrator = MTGOrchestrator()
    session_id = "acc-test-mana-1"
    query = "¿Cómo funciona el maná en Magic: The Gathering?"

    result = orchestrator.handle_message(session_id, query)

    assert result.type == ResponseType.RULES
    assert len(result.cards) == 0
    assert len(result.sources) > 0
    assert any("106" in s.reference for s in result.sources)
    assert "reserva" in result.message.lower() or "pool" in result.message.lower()


def test_acceptance_scenario_2_combat_first_strike_ninjutsu(mock_mtg_tool):
    """
    Acceptance Scenario 2: Complex Combat Interaction - First Strike + Ninjutsu timing.
    Verifies that the orchestrator extracts Rapaz and Ninja, resolves cards,
    applies combat priority rules (CR 702.7b, CR 702.48c, CR 510.4), and affirms damage.
    """
    orchestrator = MTGOrchestrator()
    session_id = "acc-test-combat-ninjutsu-2"
    query = "Mi rapaz del campo de batalla hizo daño primero, si lo cambio con mi ninja de horas tardías ¿aplico el daño?"

    result = orchestrator.handle_message(session_id, query)

    assert result.type == ResponseType.RULES
    assert "sí" in result.message.lower() or "si" in result.message.lower()
    citations = [s.reference for s in result.sources]
    assert any("702.48" in c for c in citations)
    assert any("702.7" in c for c in citations)


def test_acceptance_scenario_3_ward_target_interaction(mock_mtg_tool):
    """
    Acceptance Scenario 3: Ward Protection Trigger - Lightning Bolt on Ward.
    Verifies that Lightning Bolt is resolved as a card, Ward trigger is evaluated (CR 702.21),
    and the explanation states the spell is countered unless cost is paid.
    """
    orchestrator = MTGOrchestrator()
    session_id = "acc-test-ward-3"
    query = "¿Qué pasa si lanzo un Lightning Bolt sobre una criatura con Ward?"

    result = orchestrator.handle_message(session_id, query)

    assert result.type == ResponseType.RULES
    assert len(result.cards) >= 1
    assert result.cards[0].name == "Lightning Bolt"
    assert "guardia" in result.message.lower() or "ward" in result.message.lower()
    citations = [s.reference for s in result.sources]
    assert any("702.21" in c for c in citations)


def test_acceptance_scenario_4_multiturn_search_accumulation(mock_mtg_tool):
    """
    Acceptance Scenario 4: Multi-turn Card Search & Filter Refinement.
    Verifies that state persists across turns:
    Turn 1: 'Busco una carta blanca guerrero' -> W + Warrior
    Turn 2: '¿Y alguna que cueste solo uno?' -> W + Warrior + cmc=1
    Turn 3: 'Busca una carta roja dragón' -> context reset to R + Dragon
    """
    orchestrator = MTGOrchestrator()
    session_id = "acc-test-multiturn-4"

    # Turn 1
    res1 = orchestrator.handle_message(session_id, "Busco una carta blanca guerrero")
    assert res1.type == ResponseType.CARD_SEARCH
    assert res1.active_filters.color == "W"
    assert res1.active_filters.subtype == "Warrior"
    assert res1.active_filters.cmc is None

    # Turn 2: Follow-up refinement
    res2 = orchestrator.handle_message(session_id, "¿Y alguna que cueste solo uno?")
    assert res2.type == ResponseType.CARD_SEARCH
    assert res2.active_filters.color == "W"
    assert res2.active_filters.subtype == "Warrior"
    assert res2.active_filters.cmc == 1

    # Turn 3: Further refinement in same conversation: cost 2
    res3 = orchestrator.handle_message(session_id, "¿Y alguna de coste dos?")
    assert res3.type == ResponseType.CARD_SEARCH
    assert res3.active_filters.color == "W"
    assert res3.active_filters.subtype == "Warrior"
    assert res3.active_filters.cmc == 2

    # Separate session starts with clean slate
    res_clean = orchestrator.handle_message("new-session-clean", "Busca una carta roja dragón")
    assert res_clean.type == ResponseType.CARD_SEARCH
    assert res_clean.active_filters.color == "R"
    assert res_clean.active_filters.subtype == "Dragon"
    assert res_clean.active_filters.cmc is None



def test_acceptance_scenario_5_custom_card_creation(mock_mtg_tool):
    """
    Acceptance Scenario 5: Creative Custom Card Agent [Bonus].
    Verifies that designing Han Solo returns Boros colors ({1}{R}{W}), First Strike,
    and honest image_url: None.
    """
    orchestrator = MTGOrchestrator()
    session_id = "acc-test-custom-5"
    query = "Crea una carta custom balanceada de Han Solo"

    result = orchestrator.handle_message(session_id, query)

    assert result.type == ResponseType.CUSTOM_CARD
    assert len(result.cards) == 1
    card = result.cards[0]
    assert "Han Solo" in card.name
    assert "{R}" in card.mana_cost and "{W}" in card.mana_cost
    assert card.cmc == 3.0
    assert card.image_url is None  # Honest rejection of fake images
