from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from src.api.schemas import SourceRef, CardResult, CardSearchFilters


class Message(BaseModel):
    role: str  # user, assistant, system
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sources: List[SourceRef] = Field(default_factory=list)
    cards: List[CardResult] = Field(default_factory=list)


class ConversationContext(BaseModel):
    conversation_id: str
    messages: List[Message] = Field(default_factory=list)
    last_card_filter: Dict[str, Any] = Field(default_factory=dict)
    last_topic: Optional[str] = None  # 'rules', 'card_search', 'custom_card', 'conversation'


class ConversationMemory:
    """Manages multi-turn conversation state and filter persistence across turns."""

    def __init__(self):
        self._conversations: Dict[str, ConversationContext] = {}

    def get_or_create_conversation(self, conversation_id: str) -> ConversationContext:
        if conversation_id not in self._conversations:
            self._conversations[conversation_id] = ConversationContext(conversation_id=conversation_id)
        return self._conversations[conversation_id]

    # Alias for backwards compatibility if needed
    get_or_create_session = get_or_create_conversation

    def add_user_message(self, conversation_id: str, content: str) -> ConversationContext:
        ctx = self.get_or_create_conversation(conversation_id)
        ctx.messages.append(Message(role="user", content=content))
        return ctx

    def add_assistant_message(
        self,
        conversation_id: str,
        content: str,
        sources: Optional[List[SourceRef]] = None,
        cards: Optional[List[CardResult]] = None,
        topic: Optional[str] = None,
        card_filter: Optional[Dict[str, Any]] = None
    ):
        ctx = self.get_or_create_conversation(conversation_id)
        ctx.messages.append(Message(
            role="assistant",
            content=content,
            sources=sources or [],
            cards=cards or []
        ))
        if topic:
            ctx.last_topic = topic
        if card_filter:
            ctx.last_card_filter.update(card_filter)

    def get_recent_history(self, conversation_id: str, limit: int = 6) -> List[Message]:
        ctx = self.get_or_create_conversation(conversation_id)
        return ctx.messages[-limit:]

    def get_last_card_filter(self, conversation_id: str) -> Dict[str, Any]:
        ctx = self.get_or_create_conversation(conversation_id)
        return dict(ctx.last_card_filter)
