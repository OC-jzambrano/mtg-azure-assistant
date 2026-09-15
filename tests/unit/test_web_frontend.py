from fastapi.testclient import TestClient

from src.api.app import app


def test_standalone_frontend_and_original_assets_are_served():
    client = TestClient(app)
    page = client.get('/chat/')
    assert page.status_code == 200
    assert 'vendor/nlux-core.js' in page.text
    for asset in ['app.js', 'standalone.css', 'vendor/nova.css',
                  'vendor/ai_sidebar.css', 'vendor/nlux-core.js', 'vendor/iabotv2.png']:
        response = client.get('/chat/' + asset)
        assert response.status_code == 200
        assert response.content
