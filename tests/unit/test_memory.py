import pytest
from datetime import datetime, timezone
from src.services.memory import ConversationMemory


def test_conversation_creation():
    memory = ConversationMemory()
    ctx1 = memory.get_or_create_conversation("conv-1")
    ctx2 = memory.get_or_create_conversation("conv-2")

    assert ctx1.conversation_id == "conv-1"
    assert ctx2.conversation_id == "conv-2"
    assert ctx1 != ctx2


def test_conversation_filter_accumulation():
    memory = ConversationMemory()
    conv_id = f"conv-filter-test-{datetime.now(timezone.utc).timestamp()}"

    # Turn 1 adds color and subtype
    memory.add_assistant_message(
        conversation_id=conv_id,
        content="Encontradas cartas",
        card_filter={"color": "W", "subtype": "Warrior"}
    )
    f1 = memory.get_last_card_filter(conv_id)
    assert f1 == {"color": "W", "subtype": "Warrior"}

    # Turn 2 adds cmc without losing color or subtype
    memory.add_assistant_message(
        conversation_id=conv_id,
        content="Encontradas cartas con cmc 1",
        card_filter={"cmc": 1}
    )
    f2 = memory.get_last_card_filter(conv_id)
    assert f2 == {"color": "W", "subtype": "Warrior", "cmc": 1}


def test_conversation_history_limit():
    memory = ConversationMemory()
    conv_id = f"conv-history-test-{datetime.now(timezone.utc).timestamp()}"

    for i in range(10):
        memory.add_user_message(conv_id, f"Mensaje {i}")

    history = memory.get_recent_history(conv_id, limit=4)
    assert len(history) == 4
    assert history[-1].content == "Mensaje 9"


class FakeDatabase:
    """In-memory mock of Database for deterministic, offline testing of ConversationMemory."""

    def __init__(self):
        self.sessions = {}
        self.messages = []

    def is_reachable(self) -> bool:
        return True

    def connection(self):
        db_self = self

        class FakeConnection:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def commit(self):
                pass

            def cursor(self):
                class FakeCursor:
                    def __init__(self):
                        self._results = []

                    def __enter__(self):
                        return self

                    def __exit__(self, *args):
                        pass

                    def execute(self, query: str, params=None):
                        params = params or ()
                        if "SELECT metadata" in query:
                            sess_id = params[0]
                            sess = db_self.sessions.get(sess_id)
                            self._results = [(sess["metadata"], sess.get("last_active"))] if sess else []
                        elif "SELECT role, content" in query:
                            sess_id = params[0]
                            self._results = [
                                (m["role"], m["content"], m["tool_calls"], m["created_at"])
                                for m in db_self.messages
                                if m["session_id"] == sess_id
                            ]
                        elif "INSERT INTO chat_sessions" in query:
                            sess_id = params[0]
                            if sess_id not in db_self.sessions:
                                db_self.sessions[sess_id] = {"metadata": {}}
                        elif "UPDATE chat_sessions" in query:
                            meta_val = params[0]
                            meta = meta_val.obj if hasattr(meta_val, "obj") else (meta_val or {})
                            sess_id = params[1]
                            db_self.sessions.setdefault(sess_id, {})["metadata"] = dict(meta)
                        elif "INSERT INTO chat_messages" in query:
                            sess_id = params[0]
                            role = "user" if "'user'" in query else "assistant"
                            content = params[1]
                            tool_calls = {}
                            if len(params) > 2:
                                tc = params[2]
                                tool_calls = tc.obj if hasattr(tc, "obj") else (tc or {})
                            db_self.messages.append({
                                "session_id": sess_id,
                                "role": role,
                                "content": content,
                                "tool_calls": dict(tool_calls),
                                "created_at": datetime.now(timezone.utc),
                            })

                    def fetchone(self):
                        return self._results[0] if self._results else None

                    def fetchall(self):
                        return list(self._results)

                return FakeCursor()

        return FakeConnection()


@pytest.fixture
def fake_db():
    return FakeDatabase()


def test_conversation_persistence_across_instances(fake_db):
    conv_id = f"test-persistent-session-{datetime.now(timezone.utc).timestamp()}"
    memory1 = ConversationMemory(db=fake_db)
    memory1.add_user_message(conv_id, "Hola, busco elfos")
    memory1.add_assistant_message(
        conv_id,
        "Encontré elfos verdes",
        topic="card_search",
        card_filter={"subtype": "Elf", "color": "G"}
    )

    # Fresh memory instance simulating a separate container replica
    memory2 = ConversationMemory(db=fake_db)
    ctx = memory2.get_or_create_conversation(conv_id)
    assert len(ctx.messages) == 2
    assert ctx.messages[0].content == "Hola, busco elfos"
    assert ctx.messages[1].content == "Encontré elfos verdes"
    assert ctx.last_topic == "card_search"
    assert ctx.last_card_filter == {"subtype": "Elf", "color": "G"}

