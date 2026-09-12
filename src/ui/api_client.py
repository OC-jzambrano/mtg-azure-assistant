import os
import httpx
from typing import Dict, Any


class MTGAssistantClient:
    """HTTP Client used by the Streamlit frontend to interact with the FastAPI backend."""

    def __init__(self, base_url: str = None):
        self.base_url = (base_url or os.getenv("BACKEND_URL", "http://localhost:8000")).rstrip("/")

    def chat(self, conversation_id: str, message: str) -> Dict[str, Any]:
        """
        Sends a message to the FastAPI /api/chat endpoint adhering strictly to the contract:
        Request: {"conversation_id": ..., "message": ...}
        Response: {"conversation_id": ..., "type": ..., "message": ..., "cards": [...], "sources": [...], "active_filters": ...}
        """
        url = f"{self.base_url}/api/chat"
        payload = {
            "conversation_id": conversation_id,
            "message": message
        }

        try:
            response = httpx.post(url, json=payload, timeout=15.0)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"HTTP Error from backend: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            raise ConnectionError(f"No se pudo conectar con el backend FastAPI en {self.base_url}. ¿Está iniciado? ({e})")
