import pytest
from src.api.schemas import ResponseType


def test_health_contract(client):
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert "MTG Call Center Assistant" in data["service"]


def test_ready_contract(client):
    res = client.get("/ready")
    assert res.status_code in [200, 503]
    data = res.json()
    assert "database_reachable" in data
    assert "pgvector_ready" in data
    assert "status" in data


def test_chat_contract_rules(client):
    conversation_id = "550e8400-e29b-41d4-a716-446655440001"
    response = client.post(
        "/api/chat",
        json={
            "conversation_id": conversation_id,
            "message": "¿Cómo funciona el maná?"
        }
    )
    assert response.status_code == 200
    body = response.json()

    assert body["conversation_id"] == conversation_id
    assert body["type"] == ResponseType.RULES
    assert isinstance(body["message"], str)
    assert body["cards"] == []
    assert len(body["sources"]) > 0
    assert body["sources"][0]["kind"] == "rule"
    assert body["sources"][0]["title"] == "Magic Comprehensive Rules"
    assert body["sources"][0]["reference"].startswith("CR ")
    assert body["active_filters"] is None


def test_chat_contract_combat_rules(client):
    conversation_id = "550e8400-e29b-41d4-a716-446655440002"
    query = "Mi rapaz del campo de batalla ha hecho daño con su daña primero, si lo cambio con mi ninja de horas tardías ¿Aplico el daño?"
    response = client.post(
        "/api/chat",
        json={
            "conversation_id": conversation_id,
            "message": query
        }
    )
    assert response.status_code == 200
    body = response.json()

    assert body["conversation_id"] == conversation_id
    assert body["type"] == ResponseType.RULES
    assert "sí" in body["message"].lower() or "si" in body["message"].lower()
    references = [s["reference"] for s in body["sources"]]
    assert any("702.48" in r for r in references)
    assert any("702.7" in r for r in references)


def test_chat_contract_card_search(client, mock_mtg_tool):
    conversation_id = "550e8400-e29b-41d4-a716-446655440003"
    response = client.post(
        "/api/chat",
        json={
            "conversation_id": conversation_id,
            "message": "Busco una carta blanca guerrero"
        }
    )
    assert response.status_code == 200
    body = response.json()

    assert body["conversation_id"] == conversation_id
    assert body["type"] == ResponseType.CARD_SEARCH
    assert isinstance(body["message"], str)
    assert isinstance(body["cards"], list)
    assert len(body["cards"]) > 0
    assert body["cards"][0]["name"] == "Dragon Hunter"
    assert body["cards"][0]["mana_cost"] == "{W}"
    assert body["cards"][0]["cmc"] == 1.0
    assert "Warrior" in body["cards"][0]["type_line"]

    assert len(body["sources"]) > 0
    assert body["sources"][0]["kind"] == "external_api"
    assert body["sources"][0]["reference"] == "cards"
    assert "magicthegathering.io" in body["sources"][0]["url"]

    assert body["active_filters"] is not None
    assert body["active_filters"]["color"] == "W"
    assert body["active_filters"]["subtype"] == "Warrior"


def test_chat_contract_preserves_conversation(client, mock_mtg_tool):
    """Multi-turn acceptance test traversing FastAPI via HTTP."""
    conversation_id = "test-multi-turn-uuid"

    # Turn 1: Search white warrior
    r1 = client.post(
        "/api/chat",
        json={
            "conversation_id": conversation_id,
            "message": "Busca una carta blanca guerrero"
        }
    )
    assert r1.status_code == 200
    b1 = r1.json()
    assert b1["type"] == "card_search"
    assert b1["active_filters"]["color"] == "W"
    assert b1["active_filters"]["subtype"] == "Warrior"

    # Turn 2: Follow-up asking for cost 1 without repeating 'blanca' or 'guerrero'
    r2 = client.post(
        "/api/chat",
        json={
            "conversation_id": conversation_id,
            "message": "¿Y alguna que cueste solo uno?"
        }
    )
    assert r2.status_code == 200
    b2 = r2.json()

    assert b2["type"] == "card_search"
    assert b2["active_filters"]["color"] == "W"
    assert b2["active_filters"]["subtype"] == "Warrior"
    assert b2["active_filters"]["cmc"] == 1
    assert len(b2["cards"]) > 0
    for card in b2["cards"]:
        assert card["cmc"] == 1.0


def test_chat_contract_custom_card(client):
    conversation_id = "550e8400-e29b-41d4-a716-446655440005"
    response = client.post(
        "/api/chat",
        json={
            "conversation_id": conversation_id,
            "message": "Quiero una carta de Han Solo, blanca-roja con dañar primero"
        }
    )
    assert response.status_code == 200
    body = response.json()

    assert body["conversation_id"] == conversation_id
    assert body["type"] == ResponseType.CUSTOM_CARD
    assert "Han Solo" in body["message"]
    assert len(body["cards"]) == 1
    card = body["cards"][0]
    assert card["name"] == "Han Solo, Capitán del Halcón"
    assert card["mana_cost"] == "{1}{R}{W}"
    assert card["cmc"] == 3.0
    assert card["image_url"] is None  # Do not fake an image URL
    assert card["set_name"] is None
    assert body["sources"] == []
    assert body["active_filters"] is None


def test_chat_contract_empty_message(client):
    response = client.post(
        "/api/chat",
        json={
            "conversation_id": "test-empty",
            "message": "   "
        }
    )
    assert response.status_code in [400, 422]


def test_chat_contract_conversation_id_round_trip(client):
    test_id = "my-custom-uuid-round-trip-12345"
    response = client.post(
        "/api/chat",
        json={
            "conversation_id": test_id,
            "message": "Hola buenas tardes"
        }
    )
    assert response.status_code == 200
    body = response.json()
    assert body["conversation_id"] == test_id
    assert body["type"] == ResponseType.CONVERSATION
