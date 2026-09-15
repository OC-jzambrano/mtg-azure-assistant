from fastapi.testclient import TestClient
from pathlib import Path

from src.api.app import app


def test_standalone_frontend_and_original_assets_are_served():
    client = TestClient(app)
    page = client.get('/chat/')
    assert page.status_code == 200
    assert 'vendor/nlux-core.js' in page.text
    assert 'assets/favicon-32.png' in page.text
    assert 'assets/favicon-192.png' in page.text
    for asset in ['app.js', 'standalone.css', 'vendor/nova.css',
                  'vendor/ai_sidebar.css', 'vendor/nlux-core.js', 'vendor/iabotv2.png',
                  'assets/favicon-32.png', 'assets/favicon-192.png']:
        response = client.get('/chat/' + asset)
        assert response.status_code == 200
        assert response.content


def test_frontend_custom_card_rendering_logic():
    """
    Test G: Verify that frontend (app.js and standalone.css) supports rich rendering
    for custom cards without an image_url (clean visual placeholder, oracle_text, P/T,
    flavor_text, and no art_prompt or generator leaks).
    """
    app_js_path = Path(__file__).resolve().parents[2] / "src" / "ui" / "web" / "app.js"
    css_path = Path(__file__).resolve().parents[2] / "src" / "ui" / "web" / "standalone.css"

    app_js = app_js_path.read_text(encoding="utf-8")
    css = css_path.read_text(encoding="utf-8")

    # Verify custom card handling in app.js
    assert "card.is_custom" in app_js
    assert "custom-card" in app_js
    assert "custom-card-placeholder" in app_js
    assert "card.oracle_text" in app_js
    assert "card.power" in app_js and "card.toughness" in app_js
    assert "card.flavor_text" in app_js

    # Verify NO art prompt or AI vendor leakage in frontend logic
    assert "art_prompt" not in app_js
    assert "DALL-E" not in app_js
    assert "Midjourney" not in app_js

    # Verify CSS styling for custom cards
    assert ".result-card.custom-card" in css
    assert ".custom-card-placeholder" in css
    assert ".custom-card-oracle" in css
    assert ".custom-card-pt" in css
