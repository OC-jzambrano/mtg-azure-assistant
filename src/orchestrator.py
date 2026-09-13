import re
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from src.api.schemas import (
    ResponseType,
    SourceRef,
    CardResult,
    CardSearchFilters
)
from src.tools.mtg_api import MTGCardSearchTool, CardItem
from src.services.rules_rag import RulesRAGStore, RuleChunk
from src.services.memory import ConversationMemory
from src.agents.rules_reasoning_agent import RulesReasoningAgent
from src.agents.custom_card_agent import CustomCardAgent


class AssistantResult(BaseModel):
    type: ResponseType
    message: str
    cards: List[CardResult] = Field(default_factory=list)
    sources: List[SourceRef] = Field(default_factory=list)
    active_filters: Optional[CardSearchFilters] = None


class MTGOrchestrator:
    """
    Single pragmatic Orchestrator / Intent Router:
    1. Intent Classification (RULES, CARD_SEARCH, CUSTOM_CARD, CONVERSATION)
    2. Delegation to Specialized Agents (RulesReasoningAgent, CustomCardAgent)
    3. Tool Execution (MTG API, RAG Store)
    4. Multi-turn State Preservation
    5. Strongly typed AssistantResult domain output
    """

    def __init__(
        self,
        rag_store: Optional[RulesRAGStore] = None,
        api_tool: Optional[MTGCardSearchTool] = None,
        rules_agent: Optional[RulesReasoningAgent] = None,
        custom_card_agent: Optional[CustomCardAgent] = None
    ):
        self.rag = rag_store or RulesRAGStore()
        self.api_tool = api_tool or MTGCardSearchTool()
        self.memory = ConversationMemory()
        self.rules_agent = rules_agent or RulesReasoningAgent()
        self.custom_card_agent = custom_card_agent or CustomCardAgent()

    def classify_intent(self, message: str, last_topic: Optional[str] = None) -> ResponseType:
        msg = message.lower().strip()

        # 1. Custom Card Intent
        if any(w in msg for w in ["crea", "crear", "créame", "diseña", "inventa", "custom", "han solo"]):
            return ResponseType.CUSTOM_CARD

        # 2. Rules / Combat Interaction Intent
        rule_signals = [
            "fases", "fase", "turno", "maná", "mana", "reserva", "pool",
            "daña primero", "daño primero", "first strike", "ninjutsu", "ninja",
            "interacción", "interaccion", "reglas", "reglamento", "aplico el daño",
            "entra el daño", "hace daño", "bloqueo", "prioridad", "pila", "stack"
        ]
        if any(w in msg for w in rule_signals):
            return ResponseType.RULES

        # 3. Card Search Intent (explicit or follow-up refinement)
        search_signals = ["busco", "busca", "buscar", "carta", "cartas", "encuentra", "dime una carta"]
        if any(w in msg for w in search_signals):
            return ResponseType.CARD_SEARCH

        # Multi-turn follow-up: if previous topic was search and user asks for modification
        refine_signals = ["y alguna", "y una", "que cueste", "de coste", "solo uno", "color", "menos de"]
        if last_topic == ResponseType.CARD_SEARCH and any(w in msg for w in refine_signals):
            return ResponseType.CARD_SEARCH

        return ResponseType.CONVERSATION

    def _extract_search_filters(self, message: str, existing_filter: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extracts structured search entities and canonicalizes them into standard domain values:
        - Colors canonical: 'W', 'U', 'B', 'R', 'G'
        - Subtypes canonical: 'Warrior', 'Ninja', 'Dragon', etc.
        """
        msg = message.lower()
        filters = dict(existing_filter)

        # Canonical Colors (SPEC 11)
        color_patterns = {
            "W": [r"\bblanco\b", r"\bblanca\b", r"\bwhite\b", r"\bw\b"],
            "U": [r"\bazul\b", r"\bblue\b", r"\bu\b"],
            "B": [r"\bnegro\b", r"\bnegra\b", r"\bblack\b", r"\bb\b"],
            "R": [r"\brojo\b", r"\broja\b", r"\bred\b", r"\br\b"],
            "G": [r"\bverde\b", r"\bgreen\b", r"\bg\b"],
        }
        for code, patterns in color_patterns.items():
            if any(re.search(pat, msg) for pat in patterns):
                filters["color"] = code
                break

        # Canonical Subtypes (SPEC 11)
        subtype_patterns = {
            "Warrior": [r"\bguerrero\b", r"\bguerrera\b", r"\bwarrior\b"],
            "Ninja": [r"\bninja\b"],
            "Soldier": [r"\bsoldado\b", r"\bsoldier\b"],
            "Knight": [r"\bcaballero\b", r"\bknight\b"],
            "Wizard": [r"\bmago\b", r"\bwizard\b"],
            "Cleric": [r"\bclerigo\b", r"\bclérigo\b", r"\bcleric\b"],
            "Rogue": [r"\bpicaro\b", r"\bpícaro\b", r"\brogue\b"],
            "Dragon": [r"\bdragon\b", r"\bdragón\b"],
            "Bird": [r"\bave\b", r"\bpajaro\b", r"\bbird\b"],
            "Elf": [r"\belfo\b", r"\belf\b"],
            "Zombie": [r"\bzombie\b"],
        }
        for subtype_canonical, patterns in subtype_patterns.items():
            if any(re.search(pat, msg) for pat in patterns):
                filters["subtype"] = subtype_canonical
                break

        # CMC / Cost
        if "menos de dos" in msg or "inferior a dos" in msg or "menor a dos" in msg or "coste < 2" in msg:
            filters["max_cmc"] = 1
            filters["cmc"] = None
        elif "solo uno" in msg or "coste uno" in msg or "coste 1" in msg or "cmc 1" in msg or "un maná" in msg or "1 maná" in msg:
            filters["cmc"] = 1
            filters["max_cmc"] = None
        elif "coste dos" in msg or "coste 2" in msg:
            filters["cmc"] = 2
            filters["max_cmc"] = None

        return filters

    def handle_message(self, conversation_id: str, message: str) -> AssistantResult:
        ctx = self.memory.get_or_create_conversation(conversation_id)
        self.memory.add_user_message(conversation_id, message)

        resp_type = self.classify_intent(message, ctx.last_topic)

        if resp_type == ResponseType.RULES:
            return self._handle_rules(conversation_id, message)
        elif resp_type == ResponseType.CARD_SEARCH:
            return self._handle_card_search(conversation_id, message)
        elif resp_type == ResponseType.CUSTOM_CARD:
            return self._handle_custom_card(conversation_id, message)
        else:
            return self._handle_general(conversation_id, message)

    def _handle_rules(self, conversation_id: str, message: str) -> AssistantResult:
        rule_chunks = self.rag.retrieve_rules(message, top_k=3)
        reply, sources = self.rules_agent.run(message=message, rule_chunks=rule_chunks)

        self.memory.add_assistant_message(
            conversation_id=conversation_id,
            content=reply,
            sources=sources,
            cards=[],
            topic=ResponseType.RULES
        )

        return AssistantResult(
            type=ResponseType.RULES,
            message=reply,
            cards=[],
            sources=sources,
            active_filters=None
        )

    def _handle_card_search(self, conversation_id: str, message: str) -> AssistantResult:
        existing_filters = self.memory.get_last_card_filter(conversation_id)
        active_raw = self._extract_search_filters(message, existing_filters)

        # Query tool with canonical filters
        cards_raw = self.api_tool.search_cards(
            color=active_raw.get("color"),
            subtype=active_raw.get("subtype"),
            card_type=active_raw.get("card_type"),
            cmc=active_raw.get("cmc"),
            max_cmc=active_raw.get("max_cmc"),
            limit=4
        )

        cards: List[CardResult] = [
            CardResult(
                name=c.name,
                mana_cost=c.mana_cost or None,
                cmc=c.cmc,
                type_line=c.type_line or None,
                oracle_text=c.oracle_text or None,
                image_url=c.image_url or None,
                set_name=c.set_name or None
            )
            for c in cards_raw
        ]

        # Typed active filters object
        typed_filters = CardSearchFilters(
            color=active_raw.get("color"),
            subtype=active_raw.get("subtype"),
            card_type=active_raw.get("card_type"),
            cmc=active_raw.get("cmc"),
            max_cmc=active_raw.get("max_cmc")
        )

        filter_desc = []
        if typed_filters.color:
            filter_desc.append(f"color {typed_filters.color}")
        if typed_filters.subtype:
            filter_desc.append(f"subtipo {typed_filters.subtype}")
        if typed_filters.cmc is not None:
            filter_desc.append(f"coste exacto {typed_filters.cmc}")
        elif typed_filters.max_cmc is not None:
            filter_desc.append(f"coste <= {typed_filters.max_cmc}")

        desc_str = ", ".join(filter_desc)

        if cards:
            reply = f"He encontrado {len(cards)} cartas que cumplen tus criterios ({desc_str})."
        else:
            reply = f"No he encontrado cartas en la base de datos de MTG que coincidan con: {desc_str}."

        sources = [
            SourceRef(
                kind="external_api",
                title="Magic: The Gathering API",
                reference="cards",
                url="https://api.magicthegathering.io/v1/cards"
            )
        ]

        self.memory.add_assistant_message(
            conversation_id=conversation_id,
            content=reply,
            sources=sources,
            cards=cards,
            topic=ResponseType.CARD_SEARCH,
            card_filter=active_raw
        )

        return AssistantResult(
            type=ResponseType.CARD_SEARCH,
            message=reply,
            cards=cards,
            sources=sources,
            active_filters=typed_filters
        )

    def _handle_custom_card(self, conversation_id: str, message: str) -> AssistantResult:
        reply, custom_card = self.custom_card_agent.run(message=message)

        self.memory.add_assistant_message(
            conversation_id=conversation_id,
            content=reply,
            sources=[],
            cards=[custom_card],
            topic=ResponseType.CUSTOM_CARD
        )

        return AssistantResult(
            type=ResponseType.CUSTOM_CARD,
            message=reply,
            cards=[custom_card],
            sources=[],
            active_filters=None
        )

    def _handle_general(self, conversation_id: str, message: str) -> AssistantResult:
        reply = (
            "¡Hola! Soy tu asistente y juez de soporte para **Magic: The Gathering** del Call Center.\n\n"
            "Puedo ayudarte con:\n"
            "1. **Reglas del juego**: Fases del turno, funcionamiento del maná o la pila.\n"
            "2. **Interacciones complejas**: Dudas de combate (ej. *Dañar primero + Ninjutsu*).\n"
            "3. **Búsqueda de cartas**: Búsqueda por color, subtipos y coste vía API oficial de MTG.\n"
            "4. **Creación de cartas custom**: Diseñar cartas personalizadas y balanceadas.\n\n"
            "¿En qué puedo ayudarte?"
        )
        self.memory.add_assistant_message(
            conversation_id=conversation_id,
            content=reply,
            sources=[],
            cards=[],
            topic=ResponseType.CONVERSATION
        )
        return AssistantResult(
            type=ResponseType.CONVERSATION,
            message=reply,
            cards=[],
            sources=[],
            active_filters=None
        )
