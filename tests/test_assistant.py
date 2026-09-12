import pytest
from fastapi.testclient import TestClient
from src.api.app import app
from src.tools.mtg_api import MTGCardSearchTool, CardItem
from src.services.rules_rag import RulesRAGStore
from src.orchestrator import MTGOrchestrator

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def orchestrator():
    return MTGOrchestrator()

@pytest.fixture
def rag():
    return RulesRAGStore()

@pytest.fixture
def api_tool():
    return MTGCardSearchTool()

# 1. Test Health Endpoint
def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "MTG Call Center Assistant" in data["service"]

# 2. Test Tool Calling & Filter Mapping
def test_search_cards_filters(api_tool):
    # Tests that spanish subtypes and colors map correctly
    results = api_tool.search_cards(color="blanco", subtype="guerrero", limit=3)
    assert len(results) > 0
    assert any("Warrior" in r.type_line for r in results)

# 3. Test Search Cards Under Two Mana (Literal Client Requirement)
def test_search_cards_under_two_mana(api_tool):
    # "Busco una carta de color blanco de coste inferior a dos de mana que sea guerrero"
    results = api_tool.search_cards(color="blanco", subtype="guerrero", max_cmc=1, limit=5)
    assert len(results) > 0
    for card in results:
        assert card.cmc <= 1.0
        assert "Warrior" in card.type_line
        # Check that image URL exists
        assert card.image_url.startswith("http")

# 4. Test External API Error Handling Resiliency
def test_search_cards_api_error():
    # Pass invalid URL to test network resilience
    broken_tool = MTGCardSearchTool(base_url="https://invalid-non-existent-mtg-api.xyz/v1")
    results = broken_tool.search_cards(color="blanco", limit=2)
    # Must fail gracefully without throwing uncaught exception
    assert results == []

# 5. Test Caso A: RAG Rule Retrieval with Citations
def test_rule_retrieval_returns_sources(rag):
    chunks = rag.retrieve_rules("¿Cómo funciona el maná?", top_k=2)
    assert len(chunks) > 0
    # Must include official CR citation format
    assert any("CR 106" in c.citation for c in chunks)
    assert any("Maná" in c.title for c in chunks)

# 6. Test Combat Interaction: First Strike + Ninjutsu
def test_combat_interaction_ninjutsu(orchestrator):
    query = "Mi rapaz del campo de batalla ha hecho daño con su daña primero, si lo cambio con mi ninja de horas tardías ¿Aplico el daño?"
    res = orchestrator.handle_message("sess-test-combat", query)
    assert res["intent"] == "RULES"
    # Grounding check: must answer positively and cite both Ninjutsu and First strike rules
    assert "sí" in res["reply"].lower() or "si" in res["reply"].lower()
    assert any("702.48" in s for s in res["sources"])
    assert any("702.7" in s for s in res["sources"])

# 7. Test Intent Classification in Orchestrator
def test_router_classification(orchestrator):
    assert orchestrator.classify_intent("¿Qué fases hay en un turno?") == "RULES"
    assert orchestrator.classify_intent("Busco una carta azul instantáneo") == "CARD_SEARCH"
    assert orchestrator.classify_intent("Quiero una carta de Han Solo blanca-roja") == "CUSTOM_CARD"
    assert orchestrator.classify_intent("Hola buenas tardes") == "CONVERSATION"

# 8. Test Caso C: Multi-turn Context Preservation
def test_chat_preserves_context(orchestrator):
    session_id = "sess-multiturn"
    # Turn 1: Initial search
    t1 = orchestrator.handle_message(session_id, "Busca una carta blanca guerrero")
    assert t1["intent"] == "CARD_SEARCH"
    assert len(t1["cards"]) > 0

    # Turn 2: Follow-up refinement without repeating "blanca" or "guerrero"
    t2 = orchestrator.handle_message(session_id, "¿Y alguna que cueste solo uno?")
    assert t2["intent"] == "CARD_SEARCH"
    # Must preserve color=blanco, subtype=guerrero and add cmc=1
    filters = t2["active_filters"]
    assert filters.get("color") == "blanco"
    assert filters.get("subtype") == "guerrero"
    assert filters.get("cmc") == 1
    for card in t2["cards"]:
        assert card["cmc"] == 1.0

# 9. Test Bonus: Custom Card Generation
def test_custom_card_creation(orchestrator):
    res = orchestrator.handle_message("sess-custom", "Quiero una carta de Han Solo, blanca-roja que tenga dañar primero")
    assert res["intent"] == "CUSTOM_CARD"
    assert "Han Solo" in res["reply"]
    assert "Dañar primero" in res["reply"]
    assert len(res["cards"]) == 1
    assert "{1}{R}{W}" in res["cards"][0]["mana_cost"]
