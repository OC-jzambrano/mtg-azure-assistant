import re
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from src.api.schemas import (
    ResponseType,
    SourceRef,
    CardResult,
    CardSearchFilters
)
from src.config import settings
from src.observability.tracing import tracing
from src.tools.mtg_api import MTGCardSearchTool, CardItem, MTGAPIError
from src.services.rules_rag import RulesRAGStore, RuleChunk
from src.services.memory import ConversationMemory
from src.agents.rules_reasoning_agent import RulesReasoningAgent
from src.agents.custom_card_agent import CustomCardAgent
from src.agents.domain_guard import DomainGuard
from src.services.llm import LLMService


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
        custom_card_agent: Optional[CustomCardAgent] = None,
        llm_service: Optional[LLMService] = None,
        domain_guard: Optional[DomainGuard] = None,
        memory: Optional[ConversationMemory] = None
    ):
        self.rag = rag_store or RulesRAGStore()
        self.api_tool = api_tool or MTGCardSearchTool()
        self.memory = memory or ConversationMemory()
        self.rules_agent = rules_agent or RulesReasoningAgent()
        self.custom_card_agent = custom_card_agent or CustomCardAgent()
        self.llm = llm_service or LLMService()
        self.domain_guard = domain_guard or DomainGuard(llm_service=self.llm)

    def classify_intent(self, message: str, last_topic: Optional[str] = None) -> ResponseType:
        msg = message.lower().strip()

        # 1. Custom Card Intent
        if any(w in msg for w in ["crea", "crear", "créame", "diseña", "inventa", "custom", "han solo"]):
            return ResponseType.CUSTOM_CARD

        # Check for explicit card search requests (prioritized over incidental "mana" mentions)
        explicit_search_patterns = [
            r"\bbusc[oa]\s+(?:una\s+)?cartas?\b",
            r"\bbuscar\s+(?:una\s+)?cartas?\b",
            r"\bencuentra\s+(?:una\s+)?cartas?\b",
            r"\bdime\s+(?:una\s+)?cartas?\b",
            r"^busc[oa]\b",
            r"^buscar\b",
            r"^encuentra\b",
        ]
        is_search_request = any(re.search(pat, msg) for pat in explicit_search_patterns)

        # Distinguish rule questions (e.g. "¿cómo funciona el maná?", "¿qué pasa si...?")
        is_rule_question = any(q in msg for q in [
            "cómo funciona", "como funciona", "qué pasa si", "que pasa si",
            "qué ocurre", "que ocurre", "cuáles son", "cuales son",
            "interactúa", "interactua", "interactúan", "interactuan",
            "aplico el daño", "entra el daño", "daña primero", "daño primero",
            "fases del turno", "fases en un turno"
        ])

        if is_search_request and not is_rule_question:
            return ResponseType.CARD_SEARCH

        # 2. Rules / Combat Interaction Intent
        rule_signals = [
            "fases", "fase", "turno", "maná", "mana", "reserva", "pool",
            "daña primero", "daño primero", "first strike", "ninjutsu", "ninja",
            "interacción", "interaccion", "interactúa", "interactua", "interactúan", "interactuan",
            "reglas", "reglamento", "aplico el daño", "entra el daño", "hace daño",
            "bloqueo", "bloqueadores", "prioridad", "pila", "stack",
            "ocurre entre", "pasa si", "ward", "guardia", "robar", "roba", "robo",
            "contrarresta", "counter", "reemplazo", "replacement", "dispara", "disparada",
            "habilidad", "habilidades", "efecto", "efectos", "objetivo", "target"
        ]

        if any(w in msg for w in rule_signals):
            return ResponseType.RULES


        # 3. Card Search Intent (general signals)
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
        - Colors canonical: 'W', 'U', 'B', 'R', 'G' (supports singular and plural: rojos, rojas, etc.)
        - Subtypes canonical: 'Warrior', 'Ninja', 'Dragon', etc.
        - Cost / CMC parsing (both digits and Spanish word numbers up to 10)
        """
        msg = message.lower()
        filters = dict(existing_filter)

        # Canonical Colors (SPEC 11) - supports singular and plural
        color_patterns = {
            "W": [r"\bblancos?\b", r"\bblancas?\b", r"\bwhite\b", r"\bw\b"],
            "U": [r"\bazules?\b", r"\bblue\b", r"\bu\b"],
            "B": [r"\bnegros?\b", r"\bnegras?\b", r"\bblack\b", r"\bb\b"],
            "R": [r"\brojos?\b", r"\brojas?\b", r"\bred\b", r"\br\b"],
            "G": [r"\bverdes?\b", r"\bgreen\b", r"\bg\b"],
        }
        for code, patterns in color_patterns.items():
            if any(re.search(pat, msg) for pat in patterns):
                filters["color"] = code
                break

        # Canonical Subtypes (SPEC 11) - supports singular and plural
        subtype_patterns = {
            "Warrior": [r"\bguerrer[oa]s?\b", r"\bwarriors?\b"],
            "Ninja": [r"\bninjas?\b"],
            "Soldier": [r"\bsoldados?\b", r"\bsoldiers?\b"],
            "Knight": [r"\bcaballeros?\b", r"\bknights?\b"],
            "Wizard": [r"\bmag[oa]s?\b", r"\bwizards?\b"],
            "Cleric": [r"\bcl[eé]rig[oa]s?\b", r"\bclerics?\b"],
            "Rogue": [r"\bp[ií]car[oa]s?\b", r"\brogues?\b"],
            "Dragon": [r"\bdrag[oó]n(?:es)?\b"],
            "Bird": [r"\baves?\b", r"\bp[aá]jar[oa]s?\b", r"\bbirds?\b"],
            "Elf": [r"\belf[oa]s?\b", r"\belves\b"],
            "Zombie": [r"\bzombies?\b"],
        }
        for subtype_canonical, patterns in subtype_patterns.items():
            if any(re.search(pat, msg) for pat in patterns):
                filters["subtype"] = subtype_canonical
                break

        # Number word mapping for Spanish
        number_words = {
            "cero": 0, "un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3,
            "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7, "ocho": 8,
            "nueve": 9, "diez": 10
        }

        def _to_int(val: str) -> Optional[int]:
            if val.isdigit():
                return int(val)
            return number_words.get(val.lower())

        num_pattern = r"(\d+|cero|uno|una|un|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez)"

        # 1. Strict Less Than (< N)
        m_less = re.search(rf"(?:coste\s+)?(?:inferior|menor|menos)\s+(?:a|de|que)\s+{num_pattern}", msg)
        if not m_less:
            m_less = re.search(r"coste\s*<\s*(\d+)", msg)
        if m_less:
            val = _to_int(m_less.group(1))
            if val is not None:
                filters["max_cmc"] = max(0, val - 1)
                filters["cmc"] = None
                return filters

        # 2. Less than or equal (<= N)
        m_le = re.search(rf"(?:coste\s+)?(?:menor\s+o\s+igual|como\s+m[aá]ximo|hasta)\s+(?:a\s+)?{num_pattern}", msg)
        if not m_le:
            m_le = re.search(r"coste\s*<=\s*(\d+)", msg)
        if m_le:
            val = _to_int(m_le.group(1))
            if val is not None:
                filters["max_cmc"] = val
                filters["cmc"] = None
                return filters

        # 3. Exact Cost (== N)
        m_exact = re.search(rf"(?:coste\s+(?:exacto\s+|igual\s+a\s+|de\s+)?|cmc\s+|solo\s+){num_pattern}", msg)
        if m_exact:
            val = _to_int(m_exact.group(1))
            if val is not None:
                filters["cmc"] = val
                filters["max_cmc"] = None
                return filters

        if "un maná" in msg or "1 maná" in msg:
            filters["cmc"] = 1
            filters["max_cmc"] = None

        return filters


    def handle_message(self, conversation_id: str, message: str, locale: str = "es") -> AssistantResult:
        ctx = self.memory.get_or_create_conversation(conversation_id)
        self.memory.add_user_message(conversation_id, message)

        with tracing.observation(
            name="route_intent",
            as_type="span",
            input={"last_topic": ctx.last_topic},
            metadata={"router_type": "deterministic"}
        ) as route_obs:
            resp_type = self.classify_intent(message, ctx.last_topic)
            route_obs.update(output={"intent": resp_type.value})

        if resp_type == ResponseType.RULES:
            res = self._handle_rules(conversation_id, message)
        elif resp_type == ResponseType.CARD_SEARCH:
            res = self._handle_card_search(conversation_id, message)
        elif resp_type == ResponseType.CUSTOM_CARD:
            res = self._handle_custom_card(conversation_id, message, locale=locale)
        else:
            # ResponseType.CONVERSATION
            # Apply Soft Domain Guard (preserves last_topic and previous_user_message)
            user_messages = [m.content for m in ctx.messages[:-1] if m.role == "user"]
            prev_user_msg = user_messages[-1] if user_messages else None
            last_top = ctx.last_topic.value if hasattr(ctx.last_topic, "value") else ctx.last_topic

            guard_res = self.domain_guard.evaluate(
                message=message,
                last_topic=last_top,
                previous_user_message=prev_user_msg
            )

            if guard_res.action == "redirect":
                res = self._handle_out_of_domain(conversation_id, locale=locale)
            else:
                res = self._handle_general(conversation_id, message, locale=locale)

        with tracing.observation(
            name="build_response",
            as_type="span",
            output={
                "type": res.type.value,
                "cards_count": len(res.cards),
                "sources_count": len(res.sources)
            }
        ):
            return res

    def _extract_card_names(self, message: str) -> List[str]:
        """
        Extracts candidate card names from a rules or interaction query.
        Handles quoted names, relational phrases ('entre X y Y', 'uso X sobre Y', 'interactúa X con Y'),
        and known canonical card identifiers.
        """
        candidates: List[str] = []
        # Normalize whitespace, newlines, and tabs
        msg = re.sub(r"\s+", " ", message).strip()

        # 1. Quoted card names: "Lightning Bolt", 'Sheoldred'
        quoted = re.findall(r"[\"']([^\"']+)[\"']", msg)
        for q in quoted:
            if len(q.strip()) > 1:
                candidates.append(q.strip())

        # 2. Relational patterns:
        # Pattern: 'entre X y Y' / 'entre X e Y'
        m_entre = re.search(
            r"\bentre\s+([A-Za-zÀ-ÿ0-9\s,'-]+?)\s+(?:y|e)\s+([A-Za-zÀ-ÿ0-9\s,'-]+?)(?:\s*(?:cuando|si|en|con|al|\?|$)|$)",
            msg,
            re.IGNORECASE
        )
        if m_entre:
            c1 = re.sub(r"[?,.]$", "", m_entre.group(1)).strip()
            c2 = re.sub(r"[?,.]$", "", m_entre.group(2)).strip()
            if c1 and len(c1) > 2:
                candidates.append(c1)
            if c2 and len(c2) > 2:
                candidates.append(c2)

        # Pattern: 'interactúa X con Y' / 'interactúan X y Y'
        m_inter = re.search(
            r"\b(?:interactúa|interactua|interactúan|interactuan|ocurre entre)\s+([A-Za-zÀ-ÿ0-9\s,'-]+?)\s+(?:con|y|e)\s+([A-Za-zÀ-ÿ0-9\s,'-]+?)(?:\s*(?:cuando|si|en|\?|$)|$)",
            msg,
            re.IGNORECASE
        )
        if m_inter:
            c1 = re.sub(r"[?,.]$", "", m_inter.group(1)).strip()
            c2 = re.sub(r"[?,.]$", "", m_inter.group(2)).strip()
            if c1: candidates.append(c1)
            if c2: candidates.append(c2)

        # Pattern: 'uso X sobre Y' / 'lanzo X a Y' / 'juego X con Y'
        m_uso = re.search(
            r"\b(?:uso|usar|lanzo|lanzar|juego|jugar|casteo|castear)\s+([A-Za-zÀ-ÿ0-9\s,'-]+?)\s+(?:sobre|a|contra|hacia)\s+(?:una criatura con|un permanente con|el|la|un|una)?\s*([A-Za-zÀ-ÿ0-9\s,'-]+?)(?:\s*(?:cuando|si|en|\?|$)|$)",
            msg,
            re.IGNORECASE
        )
        if m_uso:
            c1 = re.sub(r"[?,.]$", "", m_uso.group(1)).strip()
            if c1 and len(c1) > 2:
                candidates.append(c1)

        # 3. Known canonical card names scanner
        known_keywords = [
            "battlefield raptor", "rapaz del campo de batalla",
            "ninja of the deep hours", "ninja de horas tardías", "ninja de horas tardias",
            "lightning bolt", "rayo",
            "black lotus", "loto negro",
            "sheoldred, the apocalypse", "sheoldred",
            "notion thief", "ladrón de nociones", "ladron de nociones"
        ]
        msg_lower = msg.lower()
        for kw in known_keywords:
            if kw in msg_lower:
                candidates.append(kw)

        # Deduplicate preserving order
        unique_candidates: List[str] = []
        seen = set()
        for c in candidates:
            clean = re.sub(r"^(?:mi|tu|su|un|una|el|la)\s+", "", c, flags=re.IGNORECASE).strip()
            clean = re.sub(r"[?,.!]$", "", clean).strip()
            if clean and clean.lower() not in seen:
                seen.add(clean.lower())
                unique_candidates.append(clean)

        return unique_candidates

    def _handle_rules(self, conversation_id: str, message: str) -> AssistantResult:
        # 1. Multi-source entity extraction: Identify cards mentioned in natural language
        with tracing.observation(
            name="extract_card_entities",
            as_type="span",
            output=None
        ) as extract_span:
            card_candidates = self._extract_card_names(message)
            extract_span.update(output={"candidates": card_candidates})

        resolved_cards: List[CardItem] = []
        missing_cards: List[str] = []

        if card_candidates:
            with tracing.observation(
                name="resolve_cards",
                as_type="tool",
                input={"candidates": card_candidates},
                output=None
            ) as tool_obs:
                resolved_cards, missing_cards = self.api_tool.resolve_cards(card_candidates)
                tool_obs.update(output={
                    "resolved": [c.name for c in resolved_cards],
                    "missing": missing_cards
                })

        # 2. Honest validation: If user mentions a card name that doesn't exist, do NOT hallucinate
        if missing_cards:
            missing_str = "', '".join(missing_cards)
            reply = f"No pude identificar una carta llamada '{missing_str}'. ¿Puedes comprobar el nombre?"
            self.memory.add_assistant_message(
                conversation_id=conversation_id,
                content=reply,
                sources=[],
                cards=[],
                topic=ResponseType.RULES
            )
            return AssistantResult(
                type=ResponseType.RULES,
                message=reply,
                cards=[],
                sources=[],
                active_filters=None
            )

        # Deduplicate resolved cards by name preserving order
        unique_resolved: List[CardItem] = []
        seen_resolved = set()
        for c in resolved_cards:
            if c.name.lower() not in seen_resolved:
                seen_resolved.add(c.name.lower())
                unique_resolved.append(c)
        resolved_cards = unique_resolved

        # Convert resolved CardItem to domain CardResult
        cards_typed: List[CardResult] = [
            CardResult(
                name=c.name,
                mana_cost=c.mana_cost or None,
                cmc=c.cmc,
                type_line=c.type_line or None,
                oracle_text=c.oracle_text or None,
                image_url=c.image_url or None,
                set_name=c.set_name or None
            )
            for c in resolved_cards
        ]


        # 3. Contextual RAG query expansion with verified card facts
        rag_query = message
        if cards_typed:
            card_names_str = " ".join([c.name for c in cards_typed])
            card_texts_str = " ".join([c.oracle_text or "" for c in cards_typed])
            rag_query = f"{message} {card_names_str} {card_texts_str}"

        rag_input = {"top_k": 3}
        if settings.langfuse_capture_content:
            rag_input["query"] = rag_query

        with tracing.observation(
            name="retrieve_rules",
            as_type="retriever",
            input=rag_input,
            metadata={"retrieval_backend": self.rag.last_backend_used}
        ) as ret_obs:
            rule_chunks = self.rag.retrieve_rules(rag_query, top_k=3)
            ret_obs.update(
                metadata={"retrieval_backend": self.rag.last_backend_used},
                output={
                    "count": len(rule_chunks),
                    "rules": [
                        {"rule_number": c.rule_number, "score": c.score}
                        for c in rule_chunks
                    ]
                }
            )

        # 4. Delegate to RulesReasoningAgent with both sources (Canonical Rules + Oracle Cards)
        reply, sources = self.rules_agent.run(
            message=message,
            rule_chunks=rule_chunks,
            cards=cards_typed
        )

        self.memory.add_assistant_message(
            conversation_id=conversation_id,
            content=reply,
            sources=sources,
            cards=cards_typed,
            topic=ResponseType.RULES
        )

        return AssistantResult(
            type=ResponseType.RULES,
            message=reply,
            cards=cards_typed,
            sources=sources,
            active_filters=None
        )

    def _handle_card_search(self, conversation_id: str, message: str) -> AssistantResult:
        existing_filters = self.memory.get_last_card_filter(conversation_id)

        with tracing.observation(
            name="extract_card_filters",
            as_type="span",
            output=None
        ) as filter_span:
            active_raw = self._extract_search_filters(message, existing_filters)
            filter_span.update(output={"filters": active_raw})

        search_metadata = {
            "color": active_raw.get("color"),
            "subtype": active_raw.get("subtype"),
            "cmc": active_raw.get("cmc"),
            "max_cmc": active_raw.get("max_cmc")
        }

        with tracing.observation(
            name="mtg_card_search",
            as_type="tool",
            metadata=search_metadata
        ) as search_obs:
            provider_error: Optional[MTGAPIError] = None
            try:
                cards_raw = self.api_tool.search_cards(
                    color=active_raw.get("color"),
                    subtype=active_raw.get("subtype"),
                    card_type=active_raw.get("card_type"),
                    cmc=active_raw.get("cmc"),
                    max_cmc=active_raw.get("max_cmc"),
                    limit=4
                )
                provider_status = "success" if cards_raw else "empty"
                search_obs.update(
                    output={
                        "results_count": len(cards_raw),
                        "card_names": [c.name for c in cards_raw],
                        "provider": "magicthegathering.io",
                        "provider_status": provider_status,
                        "http_status": 200,
                    }
                )
            except MTGAPIError as exc:
                provider_error = exc
                cards_raw = []
                search_obs.update(
                    level="ERROR",
                    status_message=str(exc),
                    metadata={
                        **search_metadata,
                        "provider": "magicthegathering.io",
                        "provider_status": "error",
                        "http_status": exc.status_code,
                    }
                )
            except Exception as exc:
                provider_error = MTGAPIError(str(exc))
                cards_raw = []
                search_obs.update(
                    level="ERROR",
                    status_message=str(exc),
                    metadata={
                        **search_metadata,
                        "provider": "magicthegathering.io",
                        "provider_status": "error",
                        "http_status": None,
                    }
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

        if provider_error is not None:
            color_names_es = {"W": "blanco", "U": "azul", "B": "negro", "R": "rojo", "G": "verde"}
            friendly_desc = []
            if typed_filters.color:
                c_name = color_names_es.get(typed_filters.color, typed_filters.color)
                friendly_desc.append(f"color {c_name}")
            if typed_filters.subtype:
                friendly_desc.append(f"subtipo {typed_filters.subtype}")
            if typed_filters.card_type:
                friendly_desc.append(f"tipo {typed_filters.card_type}")
            if typed_filters.cmc is not None:
                friendly_desc.append(f"coste {typed_filters.cmc}")
            elif typed_filters.max_cmc is not None:
                friendly_desc.append(f"coste <= {typed_filters.max_cmc}")

            desc_friendly_str = ", ".join(friendly_desc) if friendly_desc else "sin filtros específicos"
            reply = (
                f"No pude consultar el catálogo de Magic: The Gathering en este momento. "
                f"Tus filtros se interpretaron correctamente como {desc_friendly_str}. "
                f"Inténtalo de nuevo en unos segundos."
            )
            sources = []
        elif cards:
            reply = f"He encontrado {len(cards)} cartas que cumplen tus criterios ({desc_str})."
            sources = [
                SourceRef(
                    kind="external_api",
                    title="Magic: The Gathering API",
                    reference="cards",
                    url="https://api.magicthegathering.io/v1/cards"
                )
            ]
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

    def _handle_custom_card(self, conversation_id: str, message: str, locale: str = "es") -> AssistantResult:
        reply, custom_card = self.custom_card_agent.run(message=message, locale=locale)

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

    def _handle_general(self, conversation_id: str, message: str, locale: str = "es") -> AssistantResult:
        msg_clean = message.lower().strip()

        # 1. Overview de Magic: The Gathering
        overview_patterns = [
            r"\bde\s+qu[eé]\s+(?:se\s+)?trata\b",
            r"\ben\s+qu[eé]\s+consiste\b",
            r"\bqu[eé]\s+es\s+(?:magic(?::\s*the\s+gathering)?|mtg|este\s+juego)\b",
            r"\bc[oó]mo\s+se\s+juega\b",
        ]

        if any(re.search(pat, msg_clean) for pat in overview_patterns):
            reply = (
                "Magic: The Gathering es un juego de cartas coleccionables y estrategia. "
                "Cada jugador construye un mazo, usa tierras para generar maná, lanza "
                "criaturas y hechizos y trata de derrotar a sus oponentes; normalmente "
                "reduciendo sus vidas de 20 a 0.\n\n"
                "El turno tiene varias fases, incluyendo las fases principales y el "
                "combate. Muchas cartas pueden responder a otras mediante la pila, por "
                "lo que importan tanto la construcción del mazo, la gestión del maná "
                "como el momento en que se juega cada carta.\n\n"
                "Si quieres, puedo explicarte un turno completo o hacer una partida "
                "de ejemplo paso a paso."
            )
        else:
            # 2. Saludos cortos (sin mostrar menú completo)
            stripped = re.sub(r"^[¿¡\s]+|[?!.,\s]+$", "", msg_clean)
            greeting_patterns = [
                r"^(?:hola|buenas|buenos\s+d[ií]as|buenas\s+tardes|buenas\s+noches|hey|hi|hello|saludos|qu[eé]\s+tal)(?:\s+(?:buenas|buenos|tardes|d[ií]as|noches|asistente))?$",
            ]
            if any(re.search(pat, stripped) for pat in greeting_patterns):
                reply = (
                    "¡Hola! Soy tu asistente y juez de soporte para Magic: The Gathering. "
                    "¿En qué puedo ayudarte hoy?"
                )
            else:
                # 3. Resto de preguntas generales vía LLMService (sin invocar RulesReasoningAgent)
                system_prompt = (
                    "Eres un asistente amigable y experto en Magic: The Gathering.\n"
                    "Tu tarea es responder preguntas generales sobre el juego o conversar con el usuario.\n\n"
                    "Directrices obligatorias:\n"
                    "- Responder directamente a la pregunta.\n"
                    "- Mantener el idioma del usuario.\n"
                    "- Ser breve, claro y conciso.\n"
                    "- No inventar texto Oracle de cartas.\n"
                    "- No inventar números ni citas de Comprehensive Rules (CR).\n"
                    "- Si la consulta realmente requiere una regla concreta o resolver una interacción de juego o combate, "
                    "indícale al usuario que plantee la interacción específica con los nombres de las cartas para pasar al flujo especializado."
                )
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ]
                llm_reply = self.llm.generate_text(messages)
                if llm_reply and llm_reply.strip():
                    reply = llm_reply.strip()
                else:
                    reply = (
                        "¡Hola! Soy tu asistente de Magic: The Gathering. "
                        "Puedo ayudarte con información general, dudas de reglas e interacciones, "
                        "búsqueda de cartas oficiales o diseño de cartas personalizadas. ¿En qué puedo orientarte?"
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

    def _handle_out_of_domain(self, conversation_id: str, locale: str = "es") -> AssistantResult:
        if str(locale).lower().startswith("en"):
            reply = (
                "I specialize in **Magic: The Gathering**. I can help you with "
                "cards, rules, interactions, decks, strategy, and custom card design."
            )
        else:
            reply = (
                "Estoy especializado en **Magic: The Gathering**. Puedo ayudarte con "
                "cartas, reglas, interacciones, mazos, estrategia y diseño de cartas "
                "personalizadas."
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
