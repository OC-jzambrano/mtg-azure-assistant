from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SourceDocument:
    text: str
    source: str
    page: int | None = None
    version: str | None = None
    document_id: str | None = None


@dataclass(frozen=True)
class Chunk:
    id: str
    text: str
    metadata: dict[str, str | int]


@dataclass(frozen=True)
class RetrievedChunk:
    id: str
    text: str
    distance: float
    metadata: dict[str, str | int]


@dataclass(frozen=True)
class ChatTurn:
    user: str
    assistant: str


@dataclass
class Answer:
    text: str
    citations: list[dict[str, str | int]] = field(default_factory=list)
    abstained: bool = False
