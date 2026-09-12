import pytest
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
    conv_id = "conv-filter-test"

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
    conv_id = "conv-history-test"

    for i in range(10):
        memory.add_user_message(conv_id, f"Mensaje {i}")

    history = memory.get_recent_history(conv_id, limit=4)
    assert len(history) == 4
    assert history[-1].content == "Mensaje 9"
