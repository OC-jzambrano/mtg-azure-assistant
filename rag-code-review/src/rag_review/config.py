from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    llm_model: str = "gpt-5.6-luna"
    embedding_model: str = "text-embedding-3-small"
    chroma_path: str = "./chroma_data"
    chroma_collection: str = "docs"
    top_k: int = 5
    max_distance: float = 0.45
    chunk_size: int = 1400
    chunk_overlap: int = 200
    max_history_turns: int = 6

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required; put it in the environment, not source code.")

        settings = cls(
            openai_api_key=api_key,
            llm_model=os.getenv("OPENAI_LLM_MODEL", cls.llm_model),
            embedding_model=os.getenv("OPENAI_EMBEDDING_MODEL", cls.embedding_model),
            chroma_path=os.getenv("CHROMA_PATH", cls.chroma_path),
            chroma_collection=os.getenv("CHROMA_COLLECTION", cls.chroma_collection),
            top_k=int(os.getenv("TOP_K", cls.top_k)),
            max_distance=float(os.getenv("MAX_DISTANCE", cls.max_distance)),
            chunk_size=int(os.getenv("CHUNK_SIZE", cls.chunk_size)),
            chunk_overlap=int(os.getenv("CHUNK_OVERLAP", cls.chunk_overlap)),
            max_history_turns=int(os.getenv("MAX_HISTORY_TURNS", cls.max_history_turns)),
        )
        if settings.chunk_overlap >= settings.chunk_size:
            raise ValueError("CHUNK_OVERLAP must be smaller than CHUNK_SIZE")
        if settings.top_k <= 0:
            raise ValueError("TOP_K must be > 0")
        return settings
