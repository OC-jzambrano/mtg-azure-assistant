import pytest
import httpx
from src.tools.mtg_api import MTGCardSearchTool, CardItem


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


def test_api_error_returns_empty_list_gracefully(monkeypatch):
    """When remote API fails (500 or timeout), it must not crash."""
    def fake_get_error(self, url, params=None, headers=None):
        raise httpx.ConnectTimeout("Connection timed out")

    monkeypatch.setattr(httpx.Client, "get", fake_get_error)

    tool = MTGCardSearchTool()
    results = tool.search_cards(color="blanco")
    assert results == []
