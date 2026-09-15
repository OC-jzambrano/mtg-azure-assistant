import os
import pytest
from fastapi.testclient import TestClient
from src.api.app import app
from src.observability.tracing import tracing


@pytest.mark.integration
def test_langfuse_live_post_chat_and_flush():
    """
    Live integration test against Langfuse Cloud.
    Only runs if LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY are configured in the environment.
    """
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY", "")

    if not public_key or not secret_key:
        pytest.skip("Langfuse credentials not configured; skipping live integration test.")

    client = TestClient(app)
    response = client.post(
        "/api/chat",
        json={
            "conversation_id": "test-langfuse-live-session-1",
            "message": "¿Qué pasa si uso Lightning Bolt sobre una criatura con Ward?"
        }
    )

    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "rules"
    assert len(body["sources"]) > 0

    # Ensure flush completes without exception
    tracing.flush()
