import json
import logging
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime, timezone
import psycopg
from psycopg.types.json import Jsonb

from src.api.schemas import SourceRef, CardResult, CardSearchFilters
from src.services.database import Database, database

logger = logging.getLogger("mtg_assistant.memory")


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
    """
    Production-ready multi-turn conversation memory.
    Primary storage: PostgreSQL (chat_sessions and chat_messages tables).
    Fast L1 cache & resilient fallback: In-memory dictionary.
    Supports scaling across multiple Container Apps replicas.
    """

    def __init__(self, db: Optional[Database] = None):
        self.db = db or database
        self._conversations: Dict[str, ConversationContext] = {}

    def _db_is_available(self) -> bool:
        try:
            return self.db.is_reachable()
        except Exception:
            return False

    def get_or_create_conversation(self, conversation_id: str) -> ConversationContext:
        # Check in-memory cache first
        if conversation_id in self._conversations:
            return self._conversations[conversation_id]

        ctx = ConversationContext(conversation_id=conversation_id)

        # Attempt to load from PostgreSQL
        if self._db_is_available():
            try:
                with self.db.connection() as conn:
                    with conn.cursor() as cur:
                        # 1. Fetch session metadata
                        cur.execute(
                            """
                            SELECT metadata, last_active 
                            FROM chat_sessions 
                            WHERE session_id = %s;
                            """,
                            (conversation_id,),
                        )
                        row = cur.fetchone()
                        if row:
                            meta = row[0] or {}
                            ctx.last_topic = meta.get("last_topic")
                            ctx.last_card_filter = meta.get("last_card_filter", {})

                            # 2. Fetch recent messages
                            cur.execute(
                                """
                                SELECT role, content, tool_calls, created_at
                                FROM chat_messages
                                WHERE session_id = %s
                                ORDER BY id ASC
                                LIMIT 50;
                                """,
                                (conversation_id,),
                            )
                            for msg_row in cur.fetchall():
                                role, content, tool_calls_raw, created_at = msg_row
                                tool_calls = tool_calls_raw or {}
                                sources = [
                                    SourceRef(**s) for s in tool_calls.get("sources", [])
                                    if isinstance(s, dict)
                                ]
                                cards = [
                                    CardResult(**c) for c in tool_calls.get("cards", [])
                                    if isinstance(c, dict)
                                ]
                                ctx.messages.append(
                                    Message(
                                        role=role,
                                        content=content,
                                        timestamp=created_at or datetime.now(timezone.utc),
                                        sources=sources,
                                        cards=cards,
                                    )
                                )
                        else:
                            # Create new session record
                            cur.execute(
                                """
                                INSERT INTO chat_sessions (session_id, user_id, channel, metadata)
                                VALUES (%s, 'anonymous', 'webchat', '{}'::jsonb)
                                ON CONFLICT (session_id) DO NOTHING;
                                """,
                                (conversation_id,),
                            )
                            conn.commit()
            except Exception as exc:
                logger.debug("Failed to load conversation %s from PostgreSQL: %s", conversation_id, exc)

        self._conversations[conversation_id] = ctx
        return ctx

    # Alias for backwards compatibility if needed
    get_or_create_session = get_or_create_conversation

    def add_user_message(self, conversation_id: str, content: str) -> ConversationContext:
        ctx = self.get_or_create_conversation(conversation_id)
        msg = Message(role="user", content=content)
        ctx.messages.append(msg)

        if self._db_is_available():
            try:
                with self.db.connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            INSERT INTO chat_sessions (session_id, user_id, channel, last_active)
                            VALUES (%s, 'anonymous', 'webchat', NOW())
                            ON CONFLICT (session_id) DO UPDATE SET last_active = NOW();
                            """,
                            (conversation_id,),
                        )
                        cur.execute(
                            """
                            INSERT INTO chat_messages (session_id, role, content)
                            VALUES (%s, 'user', %s);
                            """,
                            (conversation_id, content),
                        )
                        conn.commit()
            except Exception as exc:
                logger.debug("Failed to persist user message to PostgreSQL: %s", exc)

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
        msg = Message(
            role="assistant",
            content=content,
            sources=sources or [],
            cards=cards or []
        )
        ctx.messages.append(msg)
        if topic:
            ctx.last_topic = topic
        if card_filter:
            ctx.last_card_filter.update(card_filter)

        if self._db_is_available():
            try:
                with self.db.connection() as conn:
                    with conn.cursor() as cur:
                        # Update session metadata
                        meta = {
                            "last_topic": ctx.last_topic,
                            "last_card_filter": ctx.last_card_filter,
                        }
                        cur.execute(
                            """
                            UPDATE chat_sessions 
                            SET last_active = NOW(), metadata = %s
                            WHERE session_id = %s;
                            """,
                            (Jsonb(meta), conversation_id),
                        )
                        # Insert message record with payload
                        tool_calls_payload = {
                            "sources": [s.model_dump() for s in (sources or [])],
                            "cards": [c.model_dump() for c in (cards or [])],
                        }
                        cur.execute(
                            """
                            INSERT INTO chat_messages (session_id, role, content, tool_calls)
                            VALUES (%s, 'assistant', %s, %s);
                            """,
                            (conversation_id, content, Jsonb(tool_calls_payload)),
                        )
                        conn.commit()
            except Exception as exc:
                logger.debug("Failed to persist assistant message to PostgreSQL: %s", exc)

    def get_recent_history(self, conversation_id: str, limit: int = 6) -> List[Message]:
        ctx = self.get_or_create_conversation(conversation_id)
        return ctx.messages[-limit:]

    def get_last_card_filter(self, conversation_id: str) -> Dict[str, Any]:
        ctx = self.get_or_create_conversation(conversation_id)
        return dict(ctx.last_card_filter)
