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


def test_conversation_persistence_across_instances():
    conv_id = f"test-persistent-session-{datetime.now(timezone.utc).timestamp()}"
    memory1 = ConversationMemory()
    memory1.add_user_message(conv_id, "Hola, busco elfos")
    memory1.add_assistant_message(
        conv_id,
        "Encontré elfos verdes",
        topic="card_search",
        card_filter={"subtype": "Elf", "color": "G"}
    )

    # Fresh memory instance simulating a separate container replica
    memory2 = ConversationMemory()
    ctx = memory2.get_or_create_conversation(conv_id)
    assert len(ctx.messages) == 2
    assert ctx.messages[0].content == "Hola, busco elfos"
    assert ctx.messages[1].content == "Encontré elfos verdes"
    assert ctx.last_topic == "card_search"
    assert ctx.last_card_filter == {"subtype": "Elf", "color": "G"}
