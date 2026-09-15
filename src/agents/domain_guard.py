import re
import json
import logging
from typing import Optional, Literal, Dict, Any, List
from pydantic import BaseModel, Field

from src.config import settings
from src.services.llm import LLMService
from src.observability.tracing import tracing

logger = logging.getLogger("mtg_assistant.domain_guard")


class DomainClassification(BaseModel):
    domain: Literal[
        "in_domain",
        "adjacent",
        "out_of_domain"
    ]
    confidence: float


class DomainGuardResult(BaseModel):
    domain: Literal["in_domain", "adjacent", "out_of_domain"]
    confidence: float
    action: Literal["allow", "redirect"]
    method: Literal["deterministic", "llm"]


CLASSIFIER_SYSTEM_PROMPT = (
    "Eres un clasificador de dominio para un asistente especializado en Magic: The Gathering.\n\n"
    "Clasifica la consulta como:\n\n"
    "IN_DOMAIN:\n"
    "relacionada directamente con Magic.\n\n"
    "ADJACENT:\n"
    "no menciona necesariamente Magic, pero puede ser útil para entender estrategia, probabilidad, torneos, cartas o continuar la conversación.\n\n"
    "OUT_OF_DOMAIN:\n"
    "claramente no relacionada con Magic ni con el contexto.\n\n"
    "Directrices obligatorias:\n"
    "- Sé permisivo.\n"
    "- Ante una duda razonable entre ADJACENT y OUT_OF_DOMAIN, usa ADJACENT.\n"
    "- No clasifiques como OUT_OF_DOMAIN una frase corta cuyo significado pueda depender del contexto anterior.\n"
    "- Devuelve exclusivamente los campos del esquema (domain y confidence)."
)

# Mana symbols like {W}, {U}, {B}, {R}, {G}, {C}, {X}, {1}, etc.
MANA_SYMBOL_PATTERN = re.compile(r"\{[wubrgcx0-9]+\}", re.IGNORECASE)

# Power / Toughness pattern like 2/1, 3/2, 4/4
PT_PATTERN = re.compile(r"\b\d+/\d+\b")

# Fast-path MTG Keywords
FAST_PATH_MTG_KEYWORDS: List[re.Pattern] = [
    re.compile(r"\bman[aá]\b", re.IGNORECASE),
    re.compile(r"\bcriaturas?\b", re.IGNORECASE),
    re.compile(r"\bcreatures?\b", re.IGNORECASE),
    re.compile(r"\bcartas?\b", re.IGNORECASE),
    re.compile(r"\bcards?\b", re.IGNORECASE),
    re.compile(r"\bmazos?\b", re.IGNORECASE),
    re.compile(r"\bdecks?\b", re.IGNORECASE),
    re.compile(r"\bcommanders?\b", re.IGNORECASE),
    re.compile(r"\bplaneswalkers?\b", re.IGNORECASE),
    re.compile(r"\bfirst\s+strike\b", re.IGNORECASE),
    re.compile(r"\bdañ(?:ar|o|a)\s+primero\b", re.IGNORECASE),
    re.compile(r"\bbattlefields?\b", re.IGNORECASE),
    re.compile(r"\bcampo\s+de\s+batalla\b", re.IGNORECASE),
    re.compile(r"\bcementerios?\b", re.IGNORECASE),
    re.compile(r"\bgraveyards?\b", re.IGNORECASE),
    re.compile(r"\boracle\b", re.IGNORECASE),
    re.compile(r"\bcolor\s+pie\b", re.IGNORECASE),
    re.compile(r"\btierras?\b", re.IGNORECASE),
    re.compile(r"\blands?\b", re.IGNORECASE),
    re.compile(r"\btap\b", re.IGNORECASE),
    re.compile(r"\bgirar\b", re.IGNORECASE),
    re.compile(r"\benderezar\b", re.IGNORECASE),
    re.compile(r"\buntap\b", re.IGNORECASE),
    re.compile(r"\bhechizos?\b", re.IGNORECASE),
    re.compile(r"\bspells?\b", re.IGNORECASE),
]

# Explicit Magic mentions & Greetings
MAGIC_MENTION_PATTERN = re.compile(r"\b(?:magic(?::\s*the\s+gathering)?|mtg)\b", re.IGNORECASE)
GREETING_PATTERNS = [
    re.compile(r"^(?:hola|buenas|buenos\s+d[ií]as|buenas\s+tardes|buenas\s+noches|hey|hi|hello|saludos|qu[eé]\s+tal)\b", re.IGNORECASE),
    re.compile(r"\b(?:de\s+qu[eé]\s+trata|en\s+qu[eé]\s+consiste|c[oó]mo\s+se\s+juega)\b", re.IGNORECASE)
]

# Known card names or common MTG references
KNOWN_CARD_IDENTIFIERS = [
    "dragon hunter", "sheoldred", "lightning bolt", "han solo", "gandalf",
    "darth vader", "erudito de las mareas", "black lotus", "mox", "sol ring",
    "counterspell", "jace", "chandra", "liliana", "ajani", "garruk", "teferi"
]

# Benchmark Out-of-Domain Keywords for Deterministic Fallback
OUT_OF_DOMAIN_PATTERNS = [
    # Sports / celebrities
    re.compile(r"\b(?:messi|cristiano(?:\s+ronaldo)?|ronaldo|mbapp[eé]|neymar|f[uú]tbol|soccer|baloncesto|nba|champions\s+league|bal[oó]n\s+de\s+oro)\b", re.IGNORECASE),
    # Programming / general software engineering unrelated to MTG
    re.compile(r"\b(?:api\s+rest|api\s+en\s+java|escr[ií]beme\s+(?:una\s+)?api|c[oó]digo\s+en\s+(?:java|python|c\+\+|javascript)|desarrollar\s+un\s+backend|dockerfile|kubernetes|microservicios?)\b", re.IGNORECASE),
    # Geography / trivia
    re.compile(r"\b(?:capital\s+de|pa[ií]s\s+m[aá]s|poblaci[oó]n\s+de|presidente\s+de)\b", re.IGNORECASE),
    # Health / diets
    re.compile(r"\b(?:dieta|adelgazar|perder\s+peso|rutina\s+de\s+gimnasio|calor[ií]as)\b", re.IGNORECASE),
    # Cooking recipes
    re.compile(r"\b(?:receta\s+de|c[oó]mo\s+cocinar|ingredientes\s+para)\b", re.IGNORECASE),
]

# Adjacent Concept Patterns
ADJACENT_PATTERNS = [
    re.compile(r"\b(?:probabilidad|porcentaje|calcular|tempo|random|aleatorio|suizo|torneo|mulligan|ventaja\s+de\s+cartas|estrategia|sinergia|curva\s+de\s+man[aá]|sideboard|banquillo)\b", re.IGNORECASE)
]


class DomainGuard:
    """
    Soft Domain Guard for MTG Tutor.
    Prevents the assistant from acting as a generic chatbot without being overly aggressive
    against valid queries, card game strategy, or contextual follow-ups.

    Categories:
    - IN_DOMAIN: Directly related to Magic: The Gathering.
    - ADJACENT: Card game strategy, math, probabilities, tournament logistics, or immediate context.
    - OUT_OF_DOMAIN: Clearly unrelated topics (e.g. Messi vs Cristiano, Java REST APIs, diets).

    Policy:
    - IN_DOMAIN -> allow
    - ADJACENT -> allow
    - OUT_OF_DOMAIN -> reject ONLY when confidence >= 0.85. Otherwise allow ("WHEN IN DOUBT, ALLOW").
    """

    def __init__(self, llm_service: Optional[LLMService] = None):
        self.llm = llm_service or LLMService()

    def is_fast_path_mtg_signal(
        self,
        message: str,
        last_topic: Optional[str] = None,
        previous_user_message: Optional[str] = None
    ) -> bool:
        """
        Detects obvious MTG signals to accept the query directly without LLM latency.
        """
        msg = message.strip().lower()

        # 1. Mana symbols like {W}, {U}, {B}, {R}, {G}, {1}, {2}, etc.
        if MANA_SYMBOL_PATTERN.search(message):
            return True

        # 2. Power / Toughness notation (e.g. 2/1, 3/2, 4/5)
        if PT_PATTERN.search(msg):
            return True

        # 3. Explicit MTG keywords
        if any(pat.search(msg) for pat in FAST_PATH_MTG_KEYWORDS):
            return True

        # 4. Explicit Magic / MTG mentions
        if MAGIC_MENTION_PATTERN.search(msg):
            return True

        # 5. Greetings / general bot interactions
        if any(pat.search(msg) for pat in GREETING_PATTERNS):
            return True

        # 6. Known card identifiers
        if any(card_name in msg for card_name in KNOWN_CARD_IDENTIFIERS):
            return True

        # 7. Contextual fast-path: if previous message contained resolved card or MTG signals
        # and current message has card questions (e.g. "Dragon Hunter cuesta {W}" -> "¿Y el 2/1 qué significa?")
        if previous_user_message:
            prev = previous_user_message.lower()
            if any(card_name in prev for card_name in KNOWN_CARD_IDENTIFIERS) or MANA_SYMBOL_PATTERN.search(previous_user_message):
                if PT_PATTERN.search(msg) or any(w in msg for w in ["qué significa", "que significa", "cuesta", "coste"]):
                    return True

        return False

    def _run_deterministic_fallback(
        self,
        message: str,
        last_topic: Optional[str] = None,
        previous_user_message: Optional[str] = None
    ) -> DomainClassification:
        """
        Deterministic fallback when LLM is unavailable or unconfigured.
        Follows 'WHEN IN DOUBT, ALLOW' principle.
        """
        msg = message.strip().lower()

        # Fast path signal check
        if self.is_fast_path_mtg_signal(message, last_topic, previous_user_message):
            return DomainClassification(domain="in_domain", confidence=1.0)

        # Contextual follow-up check: short queries when previous context was MTG
        topic_normalized = str(last_topic or "").lower().strip()
        has_mtg_topic = topic_normalized in ("rules", "card_search", "custom_card")
        
        words = msg.split()
        is_short_query = len(words) <= 8 or any(
            msg.startswith(prefix) for prefix in ["¿y si", "y si", "¿y eso", "y eso", "¿por qué", "por que", "¿cómo", "¿cuál", "¿cuanto"]
        )

        if has_mtg_topic and is_short_query:
            return DomainClassification(domain="in_domain", confidence=0.9)

        if previous_user_message:
            prev = previous_user_message.lower()
            prev_has_mtg = (
                any(pat.search(prev) for pat in FAST_PATH_MTG_KEYWORDS)
                or MANA_SYMBOL_PATTERN.search(previous_user_message)
                or any(w in prev for w in ["tierra", "tierras", "robar", "roba", "carta", "mazo"])
            )
            if prev_has_mtg and is_short_query:
                return DomainClassification(domain="in_domain", confidence=0.9)

        # Adjacent game/math/tournament concepts
        if any(pat.search(msg) for pat in ADJACENT_PATTERNS):
            return DomainClassification(domain="adjacent", confidence=0.9)

        # Clear Out-of-Domain benchmarks
        if any(pat.search(msg) for pat in OUT_OF_DOMAIN_PATTERNS):
            return DomainClassification(domain="out_of_domain", confidence=0.95)

        # Default fallback: When in doubt, allow as adjacent with moderate confidence
        return DomainClassification(domain="adjacent", confidence=0.6)

    def classify(
        self,
        message: str,
        last_topic: Optional[str] = None,
        previous_user_message: Optional[str] = None
    ) -> DomainClassification:
        """
        Classifies the query into IN_DOMAIN, ADJACENT, or OUT_OF_DOMAIN.
        """
        if self.is_fast_path_mtg_signal(message, last_topic, previous_user_message):
            return DomainClassification(domain="in_domain", confidence=1.0)

        if self.llm.is_available():
            topic_str = last_topic.value if hasattr(last_topic, "value") else last_topic
            context_payload = {
                "last_topic": topic_str,
                "previous_user_message": previous_user_message,
                "message": message,
            }
            try:
                parsed = self.llm.generate_structured(
                    messages=[
                        {"role": "system", "content": CLASSIFIER_SYSTEM_PROMPT},
                        {"role": "user", "content": json.dumps(context_payload, ensure_ascii=False)}
                    ],
                    response_model=DomainClassification,
                    deployment=self.llm.deployment,
                    timeout=5.0
                )
                if parsed:
                    # Sanitize confidence within [0.0, 1.0]
                    conf = max(0.0, min(1.0, float(parsed.confidence)))
                    return DomainClassification(domain=parsed.domain, confidence=conf)
            except Exception as exc:
                logger.debug("Structured domain classification failed; falling back to deterministic. %s", exc)

        return self._run_deterministic_fallback(message, last_topic, previous_user_message)

    def evaluate(
        self,
        message: str,
        last_topic: Optional[str] = None,
        previous_user_message: Optional[str] = None
    ) -> DomainGuardResult:
        """
        Evaluates the message against domain guard policies and records telemetry in Langfuse.
        """
        topic_str = last_topic.value if hasattr(last_topic, "value") else last_topic
        if topic_str is not None:
            topic_str = str(topic_str).lower().strip()

        # 1. Fast path determinista
        if self.is_fast_path_mtg_signal(message, topic_str, previous_user_message):
            classification = DomainClassification(domain="in_domain", confidence=1.0)
            method = "deterministic"
        elif self.llm.is_available():
            context_payload = {
                "last_topic": topic_str,
                "previous_user_message": previous_user_message,
                "message": message,
            }
            parsed = None
            try:
                parsed = self.llm.generate_structured(
                    messages=[
                        {"role": "system", "content": CLASSIFIER_SYSTEM_PROMPT},
                        {"role": "user", "content": json.dumps(context_payload, ensure_ascii=False)}
                    ],
                    response_model=DomainClassification,
                    deployment=self.llm.deployment,
                    timeout=5.0
                )
            except Exception as exc:
                logger.debug("Domain classification LLM call failed: %s", exc)

            if parsed:
                conf = max(0.0, min(1.0, float(parsed.confidence)))
                classification = DomainClassification(domain=parsed.domain, confidence=conf)
                method = "llm"
            else:
                classification = self._run_deterministic_fallback(message, topic_str, previous_user_message)
                method = "deterministic"
        else:
            classification = self._run_deterministic_fallback(message, topic_str, previous_user_message)
            method = "deterministic"

        # 2. Blocking Policy
        # IN_DOMAIN: allow
        # ADJACENT: allow
        # OUT_OF_DOMAIN: reject ONLY when confidence >= 0.85
        # If domain == OUT_OF_DOMAIN and confidence < 0.85 -> allow
        if classification.domain in ("in_domain", "adjacent"):
            action: Literal["allow", "redirect"] = "allow"
        elif classification.domain == "out_of_domain":
            if classification.confidence >= 0.85:
                action = "redirect"
            else:
                action = "allow"
        else:
            action = "allow"

        # 3. Observability in Langfuse
        obs_input = {
            "message": message,
            "last_topic": topic_str,
            "previous_user_message": previous_user_message
        } if settings.langfuse_capture_content else {
            "message_length": len(message),
            "last_topic": topic_str
        }

        with tracing.observation(
            name="domain_guard",
            as_type="span",
            input=obs_input,
            metadata={
                "classification": classification.domain,
                "confidence": classification.confidence,
                "last_topic": topic_str,
                "action": action,
                "method": method
            },
            output={
                "classification": classification.domain,
                "confidence": classification.confidence,
                "action": action,
                "method": method
            }
        ) as guard_obs:
            guard_obs.update(
                output={
                    "classification": classification.domain,
                    "confidence": classification.confidence,
                    "action": action,
                    "method": method
                }
            )
            return DomainGuardResult(
                domain=classification.domain,
                confidence=classification.confidence,
                action=action,
                method=method
            )
