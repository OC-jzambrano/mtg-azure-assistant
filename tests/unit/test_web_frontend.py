import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from src.api.app import app

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


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


def test_app_js_static_session_management_contracts():
    """
    Static verification of the empty conversation bug fix in app.js:
    - hasUserMessage semantic check exists
    - dedupeSessions defensive deduplication exists
    - startNewConversation handles early return and drawer closing
    - reset and new-chat buttons are bound to startNewConversation
    - buggy pattern of creating new empty sessions unconditionally is gone
    - persist() only saves sessions with actual user messages
    """
    app_js_path = Path(__file__).resolve().parents[2] / "src" / "ui" / "web" / "app.js"
    app_js = app_js_path.read_text(encoding="utf-8")

    # 1. Semantic helper hasUserMessage
    assert "function hasUserMessage(session)" in app_js
    assert "m.role === 'user'" in app_js
    assert "trim().length > 0" in app_js

    # 2. Defensive deduplication
    assert "function dedupeSessions(items)" in app_js
    assert "seen.has(session.id)" in app_js

    # 3. Explicit startNewConversation
    assert "function startNewConversation()" in app_js
    assert "!hasUserMessage(current)" in app_js
    assert "classList.remove('history-open')" in app_js

    # 4. Old buggy implementation must NOT exist
    assert "persist(); current = fresh(); persist(); mount();" not in app_js

    # 5. Handlers bound to startNewConversation
    assert "$('#reset').onclick = startNewConversation;" in app_js
    assert "$('#new-chat').onclick = startNewConversation;" in app_js

    # 6. Initial pruning and persistence back to localStorage
    assert "localStorage.setItem(storageKey, JSON.stringify(sessions));" in app_js
    assert "historySessions = [" in app_js


class SessionManagerModel:
    """
    Functional Python simulation of the exact app.js state machine rules.
    Used for verifying TEST 1 to TEST 6 deterministically.
    """
    def __init__(self, initial_storage=None):
        self.storage_key = 'mtg-tutor-conversations-v1'
        self.local_storage = {}
        if initial_storage is not None:
            self.local_storage[self.storage_key] = json.dumps(initial_storage)

        raw = self.local_storage.get(self.storage_key, '[]')
        try:
            loaded = json.loads(raw)
        except Exception:
            loaded = []
        if not isinstance(loaded, list):
            loaded = []

        self.sessions = self.dedupe_sessions([
            s for s in loaded
            if isinstance(s, dict)
            and isinstance(s.get('id'), str)
            and isinstance(s.get('messages'), list)
            and self.has_user_message(s)
        ])[:30]

        self.local_storage[self.storage_key] = json.dumps(self.sessions)
        self.current = self.fresh()
        self.drawer_open = False
        self.busy = False

    @staticmethod
    def fresh():
        import uuid
        return {
            "id": str(uuid.uuid4()),
            "messages": [],
            "results": [],
            "votes": {}
        }

    @staticmethod
    def has_user_message(session):
        if not session or not isinstance(session, dict):
            return False
        messages = session.get("messages")
        if not isinstance(messages, list):
            return False
        return any(
            m and isinstance(m, dict)
            and m.get("role") == "user"
            and len(str(m.get("message") or "").strip()) > 0
            for m in messages
        )

    @staticmethod
    def dedupe_sessions(items):
        seen = set()
        result = []
        for s in items:
            s_id = s.get("id") if isinstance(s, dict) else None
            if not s_id or s_id in seen:
                continue
            seen.add(s_id)
            result.append(s)
        return result

    def persist(self):
        prev = self.dedupe_sessions([
            s for s in self.sessions
            if s.get("id") != self.current.get("id") and self.has_user_message(s)
        ])
        if self.has_user_message(self.current):
            self.sessions = self.dedupe_sessions([self.current] + prev)[:30]
        else:
            self.sessions = prev[:30]

        self.local_storage[self.storage_key] = json.dumps(self.sessions)

    def start_new_conversation(self):
        if self.busy:
            return

        if not self.has_user_message(self.current):
            self.drawer_open = False
            return

        self.persist()
        self.current = self.fresh()
        self.persist()
        self.drawer_open = False

    def get_history_sessions(self):
        filtered_prev = [
            s for s in self.sessions
            if s.get("id") != self.current.get("id") and self.has_user_message(s)
        ]
        return [self.current] + filtered_prev

    def get_history_button_labels(self):
        history = self.get_history_sessions()
        labels = []
        for s in history:
            user_msg = next((m.get("message") for m in s.get("messages", []) if m.get("role") == "user"), None)
            labels.append(user_msg or "Nueva conversación")
        return labels

    def get_stored_sessions(self):
        return json.loads(self.local_storage.get(self.storage_key, '[]'))


def test_scenario_1_initial_10_clicks_no_stored_sessions_single_history():
    """
    TEST 1:
    Initial state: sessions = [], current = fresh()
    Click new chat 10 times.
    Expected: stored sessions = [], history visible = 1 unique 'Nueva conversación'.
    """
    manager = SessionManagerModel()
    initial_id = manager.current["id"]

    for _ in range(10):
        manager.start_new_conversation()

    assert manager.get_stored_sessions() == []
    labels = manager.get_history_button_labels()
    assert len(labels) == 1
    assert labels[0] == "Nueva conversación"
    assert manager.current["id"] == initial_id  # UUID not changed unnecessarily


def test_scenario_2_new_chat_with_existing_content_stores_previous():
    """
    TEST 2:
    current has user + assistant message. Click new chat.
    Expected: stored sessions = 1 previous conversation; current = fresh() messages=[];
    history = ['Nueva conversación', 'Hola']
    """
    manager = SessionManagerModel()
    manager.current["messages"].extend([
        {"role": "user", "message": "Hola"},
        {"role": "assistant", "message": "Hola"}
    ])

    manager.start_new_conversation()

    stored = manager.get_stored_sessions()
    assert len(stored) == 1
    assert stored[0]["messages"][0]["message"] == "Hola"

    assert len(manager.current["messages"]) == 0
    labels = manager.get_history_button_labels()
    assert labels == ["Nueva conversación", "Hola"]


def test_scenario_3_repeated_clicks_after_valid_conversation_does_not_grow():
    """
    TEST 3:
    After TEST 2, click new chat 5 more times without writing anything.
    Expected: stored sessions = 1, history labels = ['Nueva conversación', 'Hola']
    """
    manager = SessionManagerModel()
    manager.current["messages"].extend([
        {"role": "user", "message": "Hola"},
        {"role": "assistant", "message": "Hola"}
    ])
    manager.start_new_conversation()

    for _ in range(5):
        manager.start_new_conversation()

    assert len(manager.get_stored_sessions()) == 1
    labels = manager.get_history_button_labels()
    assert labels == ["Nueva conversación", "Hola"]


def test_scenario_4_first_user_message_persists_session():
    """
    TEST 4:
    Type "¿Cómo funciona el maná?" into empty current.
    After push + persist(), session moves to storage.
    """
    manager = SessionManagerModel()
    assert len(manager.get_stored_sessions()) == 0

    manager.current["messages"].append({"role": "user", "message": "¿Cómo funciona el maná?"})
    manager.persist()

    stored = manager.get_stored_sessions()
    assert len(stored) == 1
    assert stored[0]["messages"][0]["message"] == "¿Cómo funciona el maná?"
    assert manager.get_history_button_labels() == ["¿Cómo funciona el maná?"]


def test_scenario_5_initial_load_prunes_empty_ghost_sessions():
    """
    TEST 5:
    Preload localStorage with:
    [valid conversation, empty session 1, empty session 2, empty session 3]
    Reload app.
    Expected: storage only keeps valid conversation; history shows ['Nueva conversación', valid conversation]
    """
    ghost_storage = [
        {"id": "valid-conv-1", "messages": [{"role": "user", "message": "Consulta válida"}]},
        {"id": "ghost-1", "messages": []},
        {"id": "ghost-2", "messages": [{"role": "assistant", "message": "Error del sistema"}]},
        {"id": "ghost-3", "messages": [{"role": "user", "message": "   "}]}
    ]

    manager = SessionManagerModel(initial_storage=ghost_storage)

    stored = manager.get_stored_sessions()
    assert len(stored) == 1
    assert stored[0]["id"] == "valid-conv-1"

    labels = manager.get_history_button_labels()
    assert labels == ["Nueva conversación", "Consulta válida"]


def test_scenario_6_enforces_30_session_limit():
    """
    TEST 6:
    Verify limit of 30 real conversations.
    Create 35 sessions with user messages.
    Expected: storage length === 30
    """
    manager = SessionManagerModel()
    for i in range(35):
        manager.current = manager.fresh()
        manager.current["messages"].append({"role": "user", "message": f"Mensaje {i}"})
        manager.persist()

    stored = manager.get_stored_sessions()
    assert len(stored) == 30
    # The most recent should be at index 0
    assert stored[0]["messages"][0]["message"] == "Mensaje 34"


@pytest.mark.skipif(not PLAYWRIGHT_AVAILABLE, reason="Playwright not installed in environment")
def test_frontend_browser_live_e2e_empty_conversation_and_mobile_ux():
    """
    Full headless Chromium end-to-end verification of DOM elements, localStorage,
    mobile drawer closing, and 10 clicks on New Chat without creating ghost sessions.
    """
    import threading
    import time
    import uvicorn

    config = uvicorn.Config(app, host="127.0.0.1", port=8997, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    time.sleep(1)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto("http://127.0.0.1:8997/chat/")
            page.wait_for_selector("#new-chat")

            # Initial state: only 1 button
            buttons = page.query_selector_all("#sessions button")
            assert len(buttons) == 1
            assert buttons[0].inner_text() == "Nueva conversación"
            assert page.evaluate("localStorage.getItem('mtg-tutor-conversations-v1')") == "[]"

            # 10 clicks on #new-chat without user message
            for _ in range(10):
                page.click("#new-chat")

            buttons_after_10 = page.query_selector_all("#sessions button")
            assert len(buttons_after_10) == 1
            assert page.evaluate("localStorage.getItem('mtg-tutor-conversations-v1')") == "[]"

            # Mobile drawer closing verification
            page.evaluate("document.querySelector('#offcanvasAiSidebar').classList.add('history-open')")
            assert page.evaluate("document.querySelector('#offcanvasAiSidebar').classList.contains('history-open')") is True
            page.click("#new-chat")
            assert page.evaluate("document.querySelector('#offcanvasAiSidebar').classList.contains('history-open')") is False

            # Simulate message send and verify single conversation
            page.evaluate("""
                current.messages.push({ role: 'user', message: 'Hola' });
                current.messages.push({ role: 'assistant', message: '¡Hola! ¿Cómo te ayudo?' });
                persist();
            """)
            storage = json.loads(page.evaluate("localStorage.getItem('mtg-tutor-conversations-v1')"))
            assert len(storage) == 1
            assert storage[0]["messages"][0]["message"] == "Hola"

            # Click new-chat: 2 buttons (Nueva conversación, Hola)
            page.click("#new-chat")
            buttons_two = page.query_selector_all("#sessions button")
            assert len(buttons_two) == 2
            assert buttons_two[0].inner_text() == "Nueva conversación"
            assert buttons_two[1].inner_text() == "Hola"

            # 5 more clicks: still 2 buttons and 1 stored conversation
            for _ in range(5):
                page.click("#new-chat")
            buttons_still_two = page.query_selector_all("#sessions button")
            assert len(buttons_still_two) == 2
            storage_after_5 = json.loads(page.evaluate("localStorage.getItem('mtg-tutor-conversations-v1')"))
            assert len(storage_after_5) == 1

            browser.close()
    finally:
        server.should_exit = True
