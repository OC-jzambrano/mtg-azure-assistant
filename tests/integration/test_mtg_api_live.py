import pytest
from src.tools.mtg_api import MTGCardSearchTool


@pytest.mark.integration
def test_live_mtg_api_cards_search():
    """Live integration test against https://api.magicthegathering.io/v1/cards."""
    tool = MTGCardSearchTool()
    results = tool.search_cards(color="W", subtype="Warrior", max_cmc=1, limit=3)
    assert len(results) > 0
    for card in results:
        assert card.cmc <= 1.0
        assert "Warrior" in card.type_line
        assert card.image_url.startswith("http")
