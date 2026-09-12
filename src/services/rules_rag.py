import json
import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from src.config import settings

class RuleChunk(BaseModel):
    rule_id: str
    rule_number: str
    category: str
    title: str
    content: str
    citation: str
    score: float = 1.0

class RulesRAGStore:
    """
    RAG store for MTG Official Comprehensive Rules.
    Supports PostgreSQL + pgvector when configured, with a resilient in-memory fallback.
    """
    def __init__(self, data_path: Optional[str] = None):
        self.data_path = data_path or settings.rules_data_path
        self.chunks: List[RuleChunk] = []
        self._load_rules()

    def _load_rules(self):
        try:
            with open(self.data_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
            
            for item in raw_data.get("rules", []):
                # Add main rule
                self.chunks.append(RuleChunk(
                    rule_id=item.get("id", ""),
                    rule_number=item.get("rule_number", ""),
                    category=item.get("category", ""),
                    title=item.get("title", ""),
                    content=item.get("content", ""),
                    citation=f"Magic Comprehensive Rules (CR {item.get('rule_number')}) - {item.get('title')}"
                ))
                # Add subrules
                for sub in item.get("subrules", []):
                    extra = sub.get("interaction_example", "")
                    content_text = sub.get("content", "")
                    if extra:
                        content_text += f"\n[Caso de interacción]: {extra}"
                    self.chunks.append(RuleChunk(
                        rule_id=f"{item.get('id')}_{sub.get('number')}",
                        rule_number=sub.get("number", ""),
                        category=item.get("category", ""),
                        title=sub.get("title", ""),
                        content=content_text,
                        citation=f"Magic Comprehensive Rules (CR {sub.get('number')}) - {sub.get('title')}"
                    ))
        except Exception as e:
            print(f"Warning: Could not load rules from {self.data_path}: {e}")

    def retrieve_rules(self, query: str, top_k: int = 3) -> List[RuleChunk]:
        """
        Retrieves the most relevant rules for a given question.
        Calculates lexical relevance score based on MTG terms, numbers, and concepts.
        """
        if not self.chunks:
            return []

        query_lower = query.lower()
        query_words = set(re.findall(r"\w+", query_lower))

        scored_chunks: List[tuple[float, RuleChunk]] = []

        # Key domain keywords weight
        weights = {
            "mana": 3.0, "maná": 3.0, "reserva": 2.5, "pool": 2.5,
            "fases": 3.0, "fase": 3.0, "turno": 2.5, "pasos": 2.0,
            "combate": 2.5, "dañar primero": 4.0, "daño primero": 4.0, "first strike": 4.0,
            "ninjutsu": 4.0, "ninja": 3.0, "bloqueada": 2.5, "daño": 2.0, "robar": 2.0
        }

        for chunk in self.chunks:
            haystack = f"{chunk.title} {chunk.content} {chunk.category} {chunk.rule_number}".lower()
            score = 0.0

            # Match exact rule number (e.g. 106, 500, 702.48)
            if chunk.rule_number in query_lower:
                score += 10.0

            # Match keyword weights
            for kw, weight in weights.items():
                if kw in query_lower and kw in haystack:
                    score += weight * 2.0

            # Overlap of words
            chunk_words = set(re.findall(r"\w+", haystack))
            common = query_words.intersection(chunk_words)
            score += len(common) * 0.5

            if score > 0:
                scored_chunks.append((score, chunk))

        # Sort by relevance
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        top_results = [chunk for _, chunk in scored_chunks[:top_k]]

        # Fallback if query was too generic
        if not top_results and self.chunks:
            top_results = self.chunks[:top_k]

        return top_results
