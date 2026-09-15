import pytest
from fastapi.testclient import TestClient
from src.api.app import app
from src.orchestrator import MTGOrchestrator
from src.services.rules_rag import RulesRAGStore
from src.tools.mtg_api import MTGCardSearchTool, CardItem


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def sample_cards():
    return [
        CardItem(
            name="Dragon Hunter",
            mana_cost="{W}",
            cmc=1.0,
            type_line="Creature — Human Warrior",
            oracle_text="Protection from Dragons",
            image_url="http://gatherer.wizards.com/Handlers/Image.ashx?multiverseid=394541&type=card",
            rarity="Uncommon",
            set_name="Dragons of Tarkir"
        ),
        CardItem(
            name="Ornithopter",
            mana_cost="{0}",
            cmc=0.0,
            type_line="Artifact Creature — Thopter",
            oracle_text="Flying",
            image_url="http://gatherer.wizards.com/Handlers/Image.ashx?multiverseid=123&type=card",
            rarity="Common",
            set_name="Core Set"
        ),
        CardItem(
            name="Aven Skirmisher",
            mana_cost="{W}",
            cmc=1.0,
            type_line="Creature — Bird Warrior",
            oracle_text="Flying",
            image_url="http://gatherer.wizards.com/Handlers/Image.ashx?multiverseid=391797&type=card",
            rarity="Common",
            set_name="Fate Reforged"
        )
    ]


@pytest.fixture
def mock_mtg_tool(sample_cards, monkeypatch):
    """Mocks MTGCardSearchTool.search_cards so unit tests never hit the live internet."""
    def fake_search_cards(self, **kwargs):
        results = list(sample_cards)
        max_cmc = kwargs.get("max_cmc")
        cmc = kwargs.get("cmc")
        color = kwargs.get("color")
        subtype = kwargs.get("subtype")

        filtered = []
        for c in results:
            if max_cmc is not None and c.cmc > max_cmc:
                continue
            if cmc is not None and c.cmc != cmc:
                continue
            if subtype and subtype.lower() not in c.type_line.lower():
                continue
            filtered.append(c)
        return filtered

    monkeypatch.setattr(MTGCardSearchTool, "search_cards", fake_search_cards)


@pytest.fixture(autouse=True)
def prevent_external_http_in_unit_tests(monkeypatch, request):
    """
    Guarantees 100% offline, deterministic unit test execution (<1s).
    External HTTP requests are intercepted so unit tests never hang on live APIs.
    """
    if "integration" in request.keywords:
        return

    import httpx
    from src.config import settings

    monkeypatch.setattr(settings, "azure_openai_api_key", "")
    monkeypatch.setattr(settings, "openai_api_key", "")
    monkeypatch.setattr(settings, "langfuse_enabled", False)

    from src.services.llm import LLMService
    from src.services.embeddings import EmbeddingService

    def safe_llm_is_available(self):
        if getattr(self, "_client", None) is not None:
            return True
        return False

    monkeypatch.setattr(LLMService, "is_available", safe_llm_is_available)

    def safe_embed_is_available(self):
        if getattr(self, "_client", None) is not None:
            return True
        return False

    monkeypatch.setattr(EmbeddingService, "is_available", safe_embed_is_available)

    orig_get = httpx.Client.get

    def safe_get(self, url, **kwargs):
        url_str = str(url)
        # TestClient requests are either relative or target testserver
        if not url_str.startswith("http://") and not url_str.startswith("https://") or "testserver" in url_str:
            return orig_get(self, url, **kwargs)
        # Intercept external calls to ensure zero internet dependence
        return httpx.Response(status_code=200, json={"cards": []})

    monkeypatch.setattr(httpx.Client, "get", safe_get)

