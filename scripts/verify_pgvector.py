"""
Verification script for MTG Comprehensive Rules pgvector retrieval.
Verifies:
1. Live PostgreSQL connection + pgvector extension.
2. Embedding generation via Azure OpenAI (text-embedding-3-small).
3. Query retrieval for '¿Cómo funciona el maná?'
4. Strict assertions:
   - rag.last_backend_used == 'pgvector'
   - rag.last_backend_used != 'lexical_fallback'
"""
import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.services.rules_rag import RulesRAGStore
from src.orchestrator import MTGOrchestrator
from src.services.database import database
from src.services.embeddings import embedding_service


def test_pgvector_live():
    print("=" * 65)
    print("🔍 VERIFICACIÓN DE RETRIEVAL CON PGVECTOR")
    print("=" * 65)

    print("\n[1] Verificando dependencias y conectividad:")
    db_ok = database.is_available()
    emb_ok = embedding_service.is_available()
    print(f"  • PostgreSQL + pgvector disponible: {db_ok}")
    print(f"  • Servicio de Embeddings disponible: {emb_ok} (modelo: {embedding_service.deployment})")

    if not db_ok:
        raise RuntimeError("PostgreSQL no está disponible en localhost:5432.")
    if not emb_ok:
        raise RuntimeError("Servicio de Embeddings de Azure OpenAI no está configurado.")

    print("\n[2] Ejecutando consulta directa en RulesRAGStore:")
    query = "¿Cómo funciona el maná?"
    print(f"  • Consulta: '{query}'")

    rag = RulesRAGStore()
    results = rag.retrieve_rules(query, top_k=3)

    print(f"  • rag.last_backend_used: '{rag.last_backend_used}'")
    print(f"  • Reglas encontradas por similitud vectorial: {len(results)}")
    for idx, r in enumerate(results, 1):
        print(f"    {idx}. [{r.rule_number}] {r.title} (similitud de coseno: {r.score:.4f})")
        print(f"       Resumen: {r.content[:100]}...")

    # Aserciones requeridas
    assert rag.last_backend_used == "pgvector", f"FALLO: Se esperaba 'pgvector', pero se obtuvo '{rag.last_backend_used}'"
    assert rag.last_backend_used != "lexical_fallback", "FALLO: Se usó 'lexical_fallback' en vez de 'pgvector'"
    print("  ✅ COMPROBACIÓN DIRECTA EXITOSA: rag.last_backend_used es 'pgvector'.")

    print("\n[3] Ejecutando consulta a través del MTGOrchestrator:")
    orchestrator = MTGOrchestrator()
    res = orchestrator.handle_message("session-pgvector-verify", query)

    print(f"  • Intención clasificada: {res.type.value}")
    print(f"  • orchestrator.rag.last_backend_used: '{orchestrator.rag.last_backend_used}'")
    print(f"  • Fuentes oficiales citadas:")
    for s in res.sources:
        print(f"    - [{s.kind}] {s.reference}: {s.title}")

    assert orchestrator.rag.last_backend_used == "pgvector", f"FALLO en Orchestrator: {orchestrator.rag.last_backend_used}"
    assert orchestrator.rag.last_backend_used != "lexical_fallback", "FALLO: Orchestrator cayó en fallback léxico"
    print("  ✅ COMPROBACIÓN EN ORCHESTRATOR EXITOSA: rag.last_backend_used es 'pgvector'.")

    print("\n" + "=" * 65)
    print("🎯 RESULTADO FINAL: pgvector FUNCIONA CORRECTAMENTE")
    print(f"   rag.last_backend_used = '{rag.last_backend_used}' (NO 'lexical_fallback')")
    print("=" * 65)


if __name__ == "__main__":
    try:
        test_pgvector_live()
    finally:
        database.close()
