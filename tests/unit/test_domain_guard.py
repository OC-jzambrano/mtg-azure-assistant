import json
import pytest
from unittest.mock import MagicMock

from src.agents.domain_guard import (
    DomainGuard,
    DomainClassification,
    DomainGuardResult,
)
from src.services.llm import LLMService
from src.orchestrator import MTGOrchestrator
from src.api.schemas import ResponseType
from src.observability.tracing import tracing
from tests.unit.test_langfuse_pipeline import MockLangfuseClient


def test_domain_classification_schema_hygiene():
    """Verify that DomainClassification schema contains strictly domain and confidence without CoT."""
    schema = DomainClassification.model_json_schema()
    props = schema.get("properties", {})
    assert "domain" in props
    assert "confidence" in props
    assert "reasoning_steps" not in props
    assert "chain_of_thought" not in props
    assert "explanation" not in props


def test_domain_guard_messi_vs_cristiano_redirect():
    """¿Quién es mejor Messi o Cristiano? -> OUT_OF_DOMAIN -> redirect"""
    guard = DomainGuard()
    res = guard.evaluate("¿Quién es mejor Messi o Cristiano?")
    assert res.domain == "out_of_domain"
    assert res.confidence >= 0.85
    assert res.action == "redirect"


def test_domain_guard_como_funciona_una_criatura_allow():
    """¿Cómo funciona una criatura? -> IN_DOMAIN -> allow"""
    guard = DomainGuard()
    res = guard.evaluate("¿Cómo funciona una criatura?")
    assert res.domain == "in_domain"
    assert res.action == "allow"
    assert res.method == "deterministic"


def test_domain_guard_que_significa_2_1_allow():
    """¿Qué significa 2/1? -> IN_DOMAIN -> allow"""
    guard = DomainGuard()
    res = guard.evaluate("¿Qué significa 2/1?")
    assert res.domain == "in_domain"
    assert res.action == "allow"
    assert res.method == "deterministic"


def test_domain_guard_que_es_probabilidad_allow():
    """¿Qué es probabilidad? -> ADJACENT o allow"""
    guard = DomainGuard()
    res = guard.evaluate("¿Qué es probabilidad?")
    assert res.domain in ("adjacent", "in_domain")
    assert res.action == "allow"


def test_domain_guard_contextual_tierra_follow_up_allow():
    """
    Contexto:
    previous = "¿Qué probabilidad tengo de robar una tierra?"
    current = "¿Y si tengo 10?"
    -> allow
    """
    guard = DomainGuard()
    res = guard.evaluate(
        message="¿Y si tengo 10?",
        previous_user_message="¿Qué probabilidad tengo de robar una tierra?",
        last_topic="conversation"
    )
    assert res.action == "allow"
    assert res.domain in ("in_domain", "adjacent")


def test_domain_guard_contextual_dragon_hunter_pt_allow():
    """
    Contexto:
    previous = "Dragon Hunter cuesta {W}"
    current = "¿Y el 2/1 qué significa?"
    -> allow
    """
    guard = DomainGuard()
    res = guard.evaluate(
        message="¿Y el 2/1 qué significa?",
        previous_user_message="Dragon Hunter cuesta {W}",
        last_topic="rules"
    )
    assert res.action == "allow"
    assert res.domain == "in_domain"


def test_domain_guard_escribeme_api_rest_java_redirect():
    """Escríbeme una API REST en Java -> OUT_OF_DOMAIN -> redirect"""
    guard = DomainGuard()
    res = guard.evaluate("Escríbeme una API REST en Java")
    assert res.domain == "out_of_domain"
    assert res.confidence >= 0.85
    assert res.action == "redirect"


def test_domain_guard_ambiguous_with_rules_last_topic_allow():
    """
    Consulta ambigua:
    "¿Y eso por qué?" con last_topic=RULES
    -> allow
    """
    guard = DomainGuard()
    res = guard.evaluate(
        message="¿Y eso por qué?",
        last_topic="rules",
        previous_user_message=None
    )
    assert res.action == "allow"
    assert res.domain in ("in_domain", "adjacent")


def test_domain_guard_low_confidence_out_of_domain_allows():
    """
    WHEN IN DOUBT, ALLOW.
    If domain == OUT_OF_DOMAIN and confidence < 0.85 -> allow.
    """
    mock_llm = MagicMock()
    mock_llm.is_available.return_value = True
    mock_llm.generate_structured.return_value = DomainClassification(
        domain="out_of_domain",
        confidence=0.75
    )

    guard = DomainGuard(llm_service=mock_llm)
    res = guard.evaluate("Alguna consulta inusual y poco clara")
    assert res.domain == "out_of_domain"
    assert res.confidence == 0.75
    assert res.action == "allow"
    assert res.method == "llm"


def test_domain_guard_llm_structured_mock():
    """Verify structured LLM path correctly translates high confidence out-of-domain into redirect."""
    mock_llm = MagicMock()
    mock_llm.is_available.return_value = True
    mock_llm.generate_structured.return_value = DomainClassification(
        domain="out_of_domain",
        confidence=0.98
    )

    guard = DomainGuard(llm_service=mock_llm)
    res = guard.evaluate("¿Cuál es la capital de Japón?")
    assert res.domain == "out_of_domain"
    assert res.confidence == 0.98
    assert res.action == "redirect"
    assert res.method == "llm"


def test_domain_guard_fast_path_bypasses_llm():
    """Evident MTG signals must trigger deterministic fast path without calling LLM."""
    mock_llm = MagicMock()
    mock_llm.is_available.return_value = True

    guard = DomainGuard(llm_service=mock_llm)
    res = guard.evaluate("¿Por qué esta carta cuesta {W}?")
    assert res.domain == "in_domain"
    assert res.confidence == 1.0
    assert res.action == "allow"
    assert res.method == "deterministic"
    assert not mock_llm.generate_structured.called


def test_orchestrator_multi_turn_soft_domain_guard_flow():
    """
    Full end-to-end integration through MTGOrchestrator:
    1. Messi query redirects cleanly without answering or mentioning policies
    2. MTG question is answered
    3. Follow-up query in context is preserved and allowed
    4. Out-of-domain coding query redirects
    """
    orch = MTGOrchestrator()
    conv_id = "test-domain-guard-multi-turn"

    # 1. Out of domain query
    res1 = orch.handle_message(conv_id, "¿Quién es mejor Messi o Cristiano?")
    assert res1.type == ResponseType.CONVERSATION
    assert "Estoy especializado en **Magic: The Gathering**" in res1.message
    assert "Messi" not in res1.message
    assert "Cristiano" not in res1.message
    assert "política" not in res1.message.lower()
    assert "filtro" not in res1.message.lower()
    assert "modelo" not in res1.message.lower()

    # 2. In-domain question (routed directly to rules by 'robar')
    res2 = orch.handle_message(conv_id, "¿Qué probabilidad tengo de robar una tierra?")
    assert res2.type == ResponseType.RULES
    assert "Estoy especializado en **Magic: The Gathering**" not in res2.message

    # 3. Contextual follow-up (evaluated by Soft Domain Guard in CONVERSATION)
    res3 = orch.handle_message(conv_id, "¿Y si tengo 10?")
    assert res3.type == ResponseType.CONVERSATION
    assert "Estoy especializado en **Magic: The Gathering**" not in res3.message

    # 4. Out of domain programming query
    res4 = orch.handle_message(conv_id, "Escríbeme una API REST en Java")
    assert res4.type == ResponseType.CONVERSATION
    assert "Estoy especializado en **Magic: The Gathering**" in res4.message
    assert "class" not in res4.message.lower()


def test_domain_guard_observability_langfuse():
    """Verify that domain_guard observation is recorded with classification, confidence, last_topic, action, method."""
    client = MockLangfuseClient()
    tracing.set_client(client)
    try:
        orch = MTGOrchestrator()
        orch.handle_message("conv-guard-obs", "¿Quién es mejor Messi o Cristiano?")

        names = [o.name for o in client.observations]
        assert "domain_guard" in names

        guard_obs = next(o for o in client.observations if o.name == "domain_guard")
        meta = guard_obs.kwargs.get("metadata", {})
        assert meta.get("classification") == "out_of_domain"
        assert meta.get("action") == "redirect"
        assert meta.get("confidence") >= 0.85
        assert "method" in meta

        # No chain of thought
        assert "reasoning_steps" not in meta
        assert "chain_of_thought" not in meta
    finally:
        tracing.reset_client()


def test_specialized_flows_bypass_domain_guard():
    """Verify that RULES, CARD_SEARCH, and CUSTOM_CARD bypass the domain guard."""
    client = MockLangfuseClient()
    tracing.set_client(client)
    try:
        orch = MTGOrchestrator()
        # 1. RULES
        orch.handle_message("conv-bypass-rules", "¿Cómo funciona el maná?")
        names = [o.name for o in client.observations]
        assert "domain_guard" not in names

        client.observations.clear()
        # 2. CARD_SEARCH
        orch.handle_message("conv-bypass-search", "Busco un guerrero blanco")
        names = [o.name for o in client.observations]
        assert "domain_guard" not in names

        client.observations.clear()
        # 3. CUSTOM_CARD
        orch.handle_message("conv-bypass-custom", "Diseña una carta de un mago azul")
        names = [o.name for o in client.observations]
        assert "domain_guard" not in names
    finally:
        tracing.reset_client()
