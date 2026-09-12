from enum import Enum
from typing import Literal, Optional, List
from pydantic import BaseModel, Field


class ResponseType(str, Enum):
    RULES = "rules"
    CARD_SEARCH = "card_search"
    CUSTOM_CARD = "custom_card"
    CONVERSATION = "conversation"


class ChatRequest(BaseModel):
    conversation_id: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=4000)


class SourceRef(BaseModel):
    kind: Literal["rule", "external_api", "design"]
    title: str
    reference: Optional[str] = None
    url: Optional[str] = None


class CardResult(BaseModel):
    name: str
    mana_cost: Optional[str] = None
    cmc: Optional[float] = None
    type_line: Optional[str] = None
    oracle_text: Optional[str] = None
    image_url: Optional[str] = None
    set_name: Optional[str] = None


class CardSearchFilters(BaseModel):
    color: Optional[str] = None
    subtype: Optional[str] = None
    card_type: Optional[str] = None
    cmc: Optional[int] = None
    max_cmc: Optional[int] = None


class ChatResponse(BaseModel):
    conversation_id: str
    type: ResponseType
    message: str
    cards: List[CardResult] = Field(default_factory=list)
    sources: List[SourceRef] = Field(default_factory=list)
    active_filters: Optional[CardSearchFilters] = None
