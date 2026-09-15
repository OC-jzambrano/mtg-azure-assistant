import pytest
import httpx
from src.tools.mtg_api import MTGCardSearchTool, CardItem, MTGAPIError


def test_max_cmc_does_not_become_equality_filter(monkeypatch):
    """
    SPEC 10: Proves that max_cmc=1 does NOT send cmc=1 to the remote API,
    and that local filtering retains cmc=0 and cmc=1 while discarding cmc=2.
    """
    captured_params = {}

    fake_api_cards = [
        {"name": "Zero Mana Token", "cmc": 0.0, "manaCost": "{0}", "type": "Artifact Creature"},
        {"name": "One Mana Warrior", "cmc": 1.0, "manaCost": "{W}", "type": "Creature — Human Warrior"},
        {"name": "Two Mana Knight", "cmc": 2.0, "manaCost": "{1}{W}", "type": "Creature — Human Knight"}
    ]

    class FakeResponse:
        status_code = 200
        def json(self):
            return {"cards": fake_api_cards}

    def fake_get(self, url, params=None, headers=None):
        nonlocal captured_params
        captured_params = dict(params or {})
        return FakeResponse()

    monkeypatch.setattr(httpx.Client, "get", fake_get)

    tool = MTGCardSearchTool()
    results = tool.search_cards(color="blanco", subtype="guerrero", max_cmc=1, limit=5)

    # 1. API params must NOT have exact cmc="1"
    assert "cmc" not in captured_params, f"API params should not contain exact cmc when max_cmc is used: {captured_params}"

    # 2. Local filtering must retain cmc=0.0 and cmc=1.0, but drop cmc=2.0
    cmcs = [c.cmc for c in results]
    assert 0.0 in cmcs, "cmc=0.0 card must not be excluded by max_cmc=1"
    assert 1.0 in cmcs, "cmc=1.0 card must be present"
    assert 2.0 not in cmcs, "cmc=2.0 card must be filtered out by max_cmc=1"


def test_exact_cmc_is_passed_to_api(monkeypatch):
    """When exact cmc is requested, it should be passed to the API."""
    captured_params = {}

    class FakeResponse:
        status_code = 200
        def json(self):
            return {"cards": []}

    def fake_get(self, url, params=None, headers=None):
        nonlocal captured_params
        captured_params = dict(params or {})
        return FakeResponse()

    monkeypatch.setattr(httpx.Client, "get", fake_get)

    tool = MTGCardSearchTool()
    tool.search_cards(cmc=2)
    assert captured_params.get("cmc") == "2"


def test_api_timeout_raises_provider_error(monkeypatch):
    """When remote API times out, MTGAPIError must be raised."""
    def fake_get_timeout(self, url, params=None, headers=None):
        raise httpx.ConnectTimeout("Connection timed out")

    monkeypatch.setattr(httpx.Client, "get", fake_get_timeout)

    tool = MTGCardSearchTool()
    with pytest.raises(MTGAPIError) as exc_info:
        tool.search_cards(color="blanco")

    assert "timeout" in str(exc_info.value).lower()


def test_http_500_raises_provider_error(monkeypatch):
    """When remote API returns HTTP 500, MTGAPIError with status_code=500 must be raised."""
    class Fake500Response:
        status_code = 500
        def json(self):
            return {"error": "Internal Server Error"}

    def fake_get_500(self, url, params=None, headers=None):
        return Fake500Response()

    monkeypatch.setattr(httpx.Client, "get", fake_get_500)

    tool = MTGCardSearchTool()
    with pytest.raises(MTGAPIError) as exc_info:
        tool.search_cards(color="W", subtype="Warrior", cmc=1)

    assert exc_info.value.status_code == 500
    assert "500" in str(exc_info.value)


def test_http_403_raises_provider_error(monkeypatch):
    """When remote API returns HTTP 403, MTGAPIError with status_code=403 must be raised."""
    class Fake403Response:
        status_code = 403
        def json(self):
            return {"error": "Forbidden"}

    def fake_get_403(self, url, params=None, headers=None):
        return Fake403Response()

    monkeypatch.setattr(httpx.Client, "get", fake_get_403)

    tool = MTGCardSearchTool()
    with pytest.raises(MTGAPIError) as exc_info:
        tool.search_cards(color="W", subtype="Warrior", cmc=1)

    assert exc_info.value.status_code == 403
    assert "403" in str(exc_info.value)


def test_successful_empty_response_returns_empty_list(monkeypatch):
    """HTTP 200 with empty cards list must return [] without raising an exception."""
    class Fake200EmptyResponse:
        status_code = 200
        def json(self):
            return {"cards": []}

    def fake_get_empty(self, url, params=None, headers=None):
        return Fake200EmptyResponse()

    monkeypatch.setattr(httpx.Client, "get", fake_get_empty)

    tool = MTGCardSearchTool()
    results = tool.search_cards(color="W", subtype="Warrior", cmc=99)
    assert results == []


def test_exact_white_warrior_one_mana_search_contract(monkeypatch):
    """
    Contract test for the production query:
    'Busco un guerrero blanco de coste uno'
    Validates params sent to MTG API:
    - colorIdentity: 'W'
    - subtypes: 'Warrior'
    - cmc: '1'
    and validates proper parsing and CardItem extraction.
    """
    captured_params = {}

    fake_cards_payload = [
        {
            "name": "Dragon Hunter",
            "manaCost": "{W}",
            "cmc": 1.0,
            "type": "Creature — Human Warrior",
            "text": "Protection from Dragons",
            "imageUrl": "http://gatherer.wizards.com/Handlers/Image.ashx?multiverseid=394541&type=card",
            "rarity": "Uncommon",
            "setName": "Dragons of Tarkir"
        },
        {
            "name": "Aven Skirmisher",
            "manaCost": "{W}",
            "cmc": 1.0,
            "type": "Creature — Bird Warrior",
            "text": "Flying",
            "imageUrl": "http://gatherer.wizards.com/Handlers/Image.ashx?multiverseid=391797&type=card",
            "rarity": "Common",
            "setName": "Fate Reforged"
        }
    ]

    class Fake200CardsResponse:
        status_code = 200
        def json(self):
            return {"cards": fake_cards_payload}

    def fake_get_cards(self, url, params=None, headers=None):
        nonlocal captured_params
        captured_params = dict(params or {})
        return Fake200CardsResponse()

    monkeypatch.setattr(httpx.Client, "get", fake_get_cards)

    tool = MTGCardSearchTool()
    results = tool.search_cards(
        color="W",
        subtype="Warrior",
        cmc=1,
        limit=4
    )

    # 1. Verify query parameters sent to provider
    assert captured_params.get("colorIdentity") == "W"
    assert captured_params.get("subtypes") == "Warrior"
    assert captured_params.get("cmc") == "1"

    # 2. Verify returned cards
    assert len(results) == 2
    assert results[0].name == "Dragon Hunter"
    assert results[0].cmc == 1.0
    assert "Warrior" in results[0].type_line
    assert results[1].name == "Aven Skirmisher"
    assert results[1].cmc == 1.0
    assert "Warrior" in results[1].type_line
