import json
import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field

from src.config import settings

logger = logging.getLogger("mtg_assistant.rules_loader")


class RuleChunk(BaseModel):
    """
    Canonical representation of a Magic: The Gathering Comprehensive Rule chunk.
    Represents semantic units (rule or subrule) preserving domain boundaries.
    """
    rule_id: str
    rule_number: str
    category: str
    title: str
    content: str
    citation: str
    score: float = 1.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


def build_embedding_text(chunk: RuleChunk) -> str:
    """
    Formats a RuleChunk into a structured, canonical representation for embedding.
    Preserves rule number, category, title, and full semantic content.
    """
    return (
        f"Rule: CR {chunk.rule_number}\n"
        f"Category: {chunk.category}\n"
        f"Title: {chunk.title}\n\n"
        f"Content:\n{chunk.content}"
    )


def calculate_content_hash(text: str) -> str:
    """Calculates a deterministic SHA256 hex digest for idempotency checking."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_rule_chunks(path: Optional[Union[str, Path]] = None) -> List[RuleChunk]:
    """
    Loads and normalizes official MTG rules from the canonical JSON dataset.
    Returns a flat list of RuleChunk objects (main rules and subrules).
    """
    file_path = Path(path) if path else settings.rules_data_path
    chunks: List[RuleChunk] = []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        for item in raw_data.get("rules", []):
            parent_id = item.get("id", "")
            rule_number = item.get("rule_number", "")
            category = item.get("category", "")
            title = item.get("title", "")
            content = item.get("content", "")

            # 1. Add canonical main rule
            chunks.append(
                RuleChunk(
                    rule_id=parent_id,
                    rule_number=rule_number,
                    category=category,
                    title=title,
                    content=content,
                    citation=f"Magic Comprehensive Rules (CR {rule_number}) - {title}",
                    metadata={"is_subrule": False, "parent_id": parent_id},
                )
            )

            # 2. Add canonical subrules preserving hierarchical context
            for sub in item.get("subrules", []):
                sub_num = sub.get("number", "")
                sub_title = sub.get("title", "")
                content_text = sub.get("content", "")
                extra = sub.get("interaction_example", "")

                if extra:
                    content_text += f"\n[Caso de interacción]: {extra}"

                sub_id = f"{parent_id}_{sub_num}"
                chunks.append(
                    RuleChunk(
                        rule_id=sub_id,
                        rule_number=sub_num,
                        category=category,
                        title=sub_title,
                        content=content_text,
                        citation=f"Magic Comprehensive Rules (CR {sub_num}) - {sub_title}",
                        metadata={
                            "is_subrule": True,
                            "parent_id": parent_id,
                            "has_interaction_example": bool(extra),
                        },
                    )
                )

    except Exception as exc:
        logger.warning("Could not load rules from %s: %s", file_path, exc)

    return chunks
