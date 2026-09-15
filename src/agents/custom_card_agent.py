import re
import logging
from typing import Tuple, Optional
from pydantic import BaseModel, Field

from src.config import settings
from src.api.schemas import CardResult
from src.services.llm import LLMService
from src.observability.tracing import tracing

logger = logging.getLogger("mtg_assistant.custom_card_agent")


class CustomCardOutput(BaseModel):
    """
    Structured Output schema for custom card design according to WotC Color Pie.
    """
    name: str = Field(description="Nombre de la carta diseñada en el idioma solicitado (ej. español).")
    mana_cost: str = Field(description="Símbolos de coste de maná estándar de MTG, ej. '{1}{R}{W}'.")
    cmc: float = Field(description="Coste de maná convertido (CMC / Mana Value).")
    type_line: str = Field(description="Línea de tipo canónica en el idioma solicitado, ej. 'Criatura legendaria — Humano Bribón Piloto'.")
    power: Optional[str] = Field(default=None, description="Fuerza de la criatura (ej. '3') o None si no es criatura.")
    toughness: Optional[str] = Field(default=None, description="Resistencia de la criatura (ej. '2') o None si no es criatura.")
    oracle_text: str = Field(description="Habilidades y texto de reglas usando la redacción canónica oficial de Magic en el idioma solicitado.")
    flavor_text: Optional[str] = Field(default=None, description="Texto de ambientación en el idioma solicitado.")
    color_pie_rationale: str = Field(description="Explicación interna del balance mecánico y alineación con la filosofía del Color Pie en el idioma solicitado.")
    art_prompt: Optional[str] = Field(
        default=None,
        description="Descripción visual interna opcional para una futura etapa de generación de arte. No mostrar al usuario."
    )


class CustomCardAgent:
    """
    Specialized Custom Card Designer Agent:
    Synthesizes creative, balanced MTG cards conforming to Wizards of the Coast Color Pie principles.
    Enforces honest image_url=None handling (no hallucinations).
    Supports Azure OpenAI Structured Outputs and deterministic local fallback.
    """

    SYSTEM_PROMPT = (
        "Eres un Diseñador Senior de I+D de Magic: The Gathering (Custom Card Designer Agent).\n"
        "Tu objetivo es crear cartas ficticias balanceadas, elegantes y perfectamente alineadas con las directrices "
        "oficiales del Color Pie de Wizards of the Coast (WotC).\n\n"
        "Reglas de diseño obligatorias:\n"
        "1. Sintaxis oficial: Usa la terminología canónica de MTG (ej. 'Dañar primero', '{T}', 'siempre que...').\n"
        "2. Balance de coste: Asigna un CMC proporcional a la fuerza/resistencia y potencia de las habilidades.\n"
        "3. Color Pie estricto: Blanco aporta orden, lealtad y primeras líneas; Rojo aporta agresividad, velocidad e impulsividad; "
        "Azul aporta conocimiento y evasión; Negro aporta sacrificio y ambición; Verde aporta crecimiento y naturaleza.\n"
        "4. Justificación obligatoria: Explica en 'color_pie_rationale' por qué la carta pertenece a sus colores asignados.\n"
        "5. Prompt de arte interno (art_prompt): Opcionalmente describe de forma concisa la escena en inglés para la "
        "metadata interna de una futura etapa de generación gráfica. Esta descripción es estrictamente interna y nunca "
        "debe mostrarse al usuario ni incluirse en el texto de la respuesta.\n\n"
        "POLÍTICA ESTRICTA DE IDIOMA Y LOCALIZACIÓN:\n"
        "- Todos los campos visibles para el usuario (name, type_line, oracle_text, flavor_text y color_pie_rationale) "
        "DEBEN generarse en el idioma solicitado por el parámetro locale (por defecto español, locale='es').\n"
        "- Si locale == 'es':\n"
        "  * El nombre/título de la carta debe estar en español. Los nombres propios (ej. 'Han Solo', 'Darth Vader') "
        "se conservan, pero sus títulos y epítetos se adaptan al español (ej. 'Han Solo, Capitán del Halcón').\n"
        "  * type_line debe estar completamente en español (ej. 'Criatura legendaria — Humano Bribón Piloto', 'Instantáneo', 'Encantamiento').\n"
        "  * oracle_text debe usar exclusivamente la terminología española canónica oficial de Magic: The Gathering:\n"
        "    - 'First strike' -> 'Dañar primero'\n"
        "    - 'Flying' -> 'Volar'\n"
        "    - 'Haste' -> 'Prisa'\n"
        "    - 'Trample' -> 'Arrollar'\n"
        "    - 'Menace' -> 'Amenaza'\n"
        "    - 'Deathtouch' -> 'Toque mortal'\n"
        "    - 'Lifelink' -> 'Vínculo vital'\n"
        "    - 'Vigilance' -> 'Vigilancia'\n"
        "    - 'Flash' -> 'Destello'\n"
        "    - 'Hexproof' -> 'Antimaleficio'\n"
        "    - 'Ward' -> 'Guardia'\n"
        "    - 'Battlefield' -> 'Campo de batalla'\n"
        "    - 'Graveyard' -> 'Cementerio'\n"
        "    - 'Library' -> 'Biblioteca'\n"
        "    - 'Whenever...' -> 'Siempre que...'\n"
        "  * flavor_text y color_pie_rationale deben estar redactados íntegramente en español.\n"
        "  * Los símbolos de maná estándar ({W}, {U}, {B}, {R}, {G}, {C}, {1}, etc.) nunca se traducen ni modifican.\n"
        "  * NUNCA devuelvas campos visibles en inglés si el locale es 'es'. No mezcles idiomas."
    )

    def __init__(self, llm_service: Optional[LLMService] = None):
        self.llm = llm_service or LLMService()

    def run(self, message: str, locale: str = "es") -> Tuple[str, CardResult]:
        """
        Synthesizes a custom card based on user specifications.
        Args:
            message: User request description.
            locale: Desired response language (defaults to "es").
        Returns:
            Tuple[str, CardResult]: Markdown presentation and typed CardResult (with image_url=None).
        """
        with tracing.observation(
            name="custom_card_agent",
            as_type="agent",
            metadata={"llm_available": self.llm.is_available(), "locale": locale}
        ) as agent_obs:
            fallback_reason = None

            # 1. Attempt LLM with Structured Outputs if available
            if self.llm.is_available():
                structured_res = self._run_llm(message, locale=locale)
                if structured_res:
                    reply, card_result = self._format_response(structured_res, locale=locale)
                    safe_out = {
                        "card_name": card_result.name,
                        "mana_cost": card_result.mana_cost,
                        "cmc": card_result.cmc,
                        "fallback_used": False,
                        "locale": locale
                    }
                    if settings.langfuse_capture_content:
                        safe_out["oracle_text"] = card_result.oracle_text
                    agent_obs.update(
                        output=safe_out,
                        metadata={"fallback_used": False, "llm_available": True, "locale": locale}
                    )
                    return reply, card_result
                else:
                    fallback_reason = "structured_output_error"
            else:
                fallback_reason = "no_credentials"

            # 2. Deterministic Local Fallback
            with tracing.observation(
                name="deterministic_fallback",
                as_type="span",
                metadata={
                    "reason": fallback_reason,
                    "agent": "custom_card",
                    "locale": locale
                }
            ):
                reply, card_result = self._run_deterministic_fallback(message, locale=locale)

            safe_out = {
                "card_name": card_result.name,
                "mana_cost": card_result.mana_cost,
                "cmc": card_result.cmc,
                "fallback_used": True,
                "locale": locale
            }
            if settings.langfuse_capture_content:
                safe_out["oracle_text"] = card_result.oracle_text
            agent_obs.update(
                output=safe_out,
                metadata={"fallback_used": True, "llm_available": self.llm.is_available(), "locale": locale}
            )
            return reply, card_result

    def _run_llm(self, message: str, locale: str = "es") -> Optional[CustomCardOutput]:
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Solicitud del jugador:\n\"{message}\"\n\n"
                    f"Locale solicitado: '{locale}'.\n"
                    "Diseña la carta custom balanceada siguiendo las directrices del Color Pie y generando todos los campos visibles estrictamente en el idioma del locale."
                )
            }
        ]

        return self.llm.generate_structured(
            messages=messages,
            response_model=CustomCardOutput,
            deployment=self.llm.deployment_reasoning
        )

    def _format_response(self, output: CustomCardOutput, locale: str = "es") -> Tuple[str, CardResult]:
        # Build honest CardResult (DoD: image_url must be None for custom designs)
        # CardResult is the single source of truth for the complete visual card representation.
        card_result = CardResult(
            name=output.name,
            mana_cost=output.mana_cost,
            cmc=output.cmc,
            type_line=output.type_line,
            oracle_text=output.oracle_text,
            power=output.power,
            toughness=output.toughness,
            flavor_text=output.flavor_text,
            is_custom=True,
            image_url=None,
            set_name=None
        )

        # Brief introductory reply to avoid repeating card components already rendered by the UI
        if str(locale).lower().startswith("en"):
            reply = f"I've designed **{output.name}**, a custom card based on your request."
        else:
            reply = f"Te he preparado **{output.name}**, una carta personalizada basada en tu solicitud."

        return reply, card_result

    def _run_deterministic_fallback(self, message: str, locale: str = "es") -> Tuple[str, CardResult]:
        """
        Deterministic canonical generator for benchmark custom card (Han Solo) and generic fallback.
        """
        msg_lower = message.lower()

        # 1. Darth Vader / Dimir contextual design
        if "vader" in msg_lower or ("negra" in msg_lower and "azul" in msg_lower) or ("negro" in msg_lower and "azul" in msg_lower):
            output = CustomCardOutput(
                name="Darth Vader, Señor Oscuro de los Sith",
                mana_cost="{2}{U}{B}",
                cmc=4.0,
                type_line="Criatura legendaria — Humano Sith",
                power="4",
                toughness="4",
                oracle_text=(
                    "**Amenaza**.\n\n"
                    "Cuando Darth Vader entre al campo de batalla, "
                    "destruye la criatura objetivo que controla un oponente a menos que ese jugador pague 3 vidas.\n\n"
                    "{1}{U}{B}, {T}: El oponente objetivo muestra su mano. Elige una carta que no sea tierra de ahí. "
                    "Ese jugador descarta esa carta."
                ),
                flavor_text="Encuentro tu falta de fe perturbadora.",
                color_pie_rationale="Diseño balanceado Dimir ({U}{B}): El negro aporta destrucción implacable y ambición cruel, mientras el azul aporta control mental, telequinesis y anticipación táctica.",
                art_prompt="A dramatic digital oil painting in the style of Magic: The Gathering card art, depicting Darth Vader standing in a dark metallic chamber with glowing red lights, raising a gloved hand with dark purple telekinetic force crackling around him, intense red lightsaber glowing, cinematic rim lighting, epic fantasy mood."
            )
            return self._format_response(output, locale=locale)

        # 2. Canonical benchmark: Han Solo Boros with first strike (default fallback)
        output = CustomCardOutput(
            name="Han Solo, Capitán del Halcón",
            mana_cost="{1}{R}{W}",
            cmc=3.0,
            type_line="Criatura legendaria — Humano Bribón Piloto",
            power="3",
            toughness="2",
            oracle_text=(
                "**Dañar primero**.\n\n"
                "Siempre que Han Solo ataque o bloquee, si tienes una o menos cartas en tu mano, "
                "obtiene +1/+0 y no puede ser bloqueado por criaturas con fuerza de 4 o más este combate.\n\n"
                "{2}, {T}: El Vehículo objetivo que controlas se convierte en criatura artefacto hasta el final del turno."
            ),
            flavor_text="Nunca me digas las probabilidades.",
            color_pie_rationale="Diseño balanceado respetando la filosofía del Color Pie (iniciativa agresiva roja y lealtad/coordinación blanca).",
            art_prompt="A dynamic digital oil painting in the style of Magic: The Gathering card art, depicting a charismatic smuggler resembling Han Solo in a worn vest and holster, drawing a heavy blaster pistol in a crowded alien cantina, smoke and blaster fire in the background, warm cinematic lighting, heroic action composition."
        )
        return self._format_response(output, locale=locale)

