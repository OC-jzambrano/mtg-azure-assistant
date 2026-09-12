from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime, timezone

class Message(BaseModel):
    role: str # user, assistant, system
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sources: Optional[List[str]] = None
    cards: Optional[List[Dict[str, Any]]] = None

class SessionContext(BaseModel):
    session_id: str
    messages: List[Message] = Field(default_factory=list)
    last_card_filter: Dict[str, Any] = Field(default_factory=dict)
    last_topic: Optional[str] = None # 'rules', 'search', 'custom_card'

class ConversationMemory:
    """Manages multi-turn conversation state and filter persistence across turns."""
    
    def __init__(self):
        self._sessions: Dict[str, SessionContext] = {}

    def get_or_create_session(self, session_id: str) -> SessionContext:
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionContext(session_id=session_id)
        return self._sessions[session_id]

    def add_user_message(self, session_id: str, content: str) -> SessionContext:
        session = self.get_or_create_session(session_id)
        session.messages.append(Message(role="user", content=content))
        return session

    def add_assistant_message(
        self,
        session_id: str,
        content: str,
        sources: Optional[List[str]] = None,
        cards: Optional[List[Dict[str, Any]]] = None,
        topic: Optional[str] = None,
        card_filter: Optional[Dict[str, Any]] = None
    ):
        session = self.get_or_create_session(session_id)
        session.messages.append(Message(
            role="assistant",
            content=content,
            sources=sources,
            cards=cards
        ))
        if topic:
            session.last_topic = topic
        if card_filter:
            # Merge with existing filters
            session.last_card_filter.update(card_filter)

    def get_recent_history(self, session_id: str, limit: int = 6) -> List[Message]:
        session = self.get_or_create_session(session_id)
        return session.messages[-limit:]

    def get_last_card_filter(self, session_id: str) -> Dict[str, Any]:
        session = self.get_or_create_session(session_id)
        return dict(session.last_card_filter)
