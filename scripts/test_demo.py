import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.observability.tracing import tracing
from src.orchestrator import MTGOrchestrator
from tests.unit.test_langfuse_pipeline import MockLangfuseClient


def run_demo():
    # 1. Configurar cliente observador
    mock_client = MockLangfuseClient()
    tracing.set_client(mock_client)

    orchestrator = MTGOrchestrator()
    conversation_id = "test-session-demo"
    mensaje = "¿Qué pasa si uso Lightning Bolt sobre una criatura con Ward?"

    print("=" * 60)
    print("🚀 EJECUTANDO TURNO DE CHAT CON LANGFUSE OBSERVABILITY")
    print("=" * 60)
    print(f"Session ID (conversation_id): {conversation_id}")
    print(f"Mensaje del usuario:          {mensaje}\n")

    # 2. Ejecutar dentro de la traza raíz
    with tracing.chat_trace(conversation_id=conversation_id, message=mensaje) as trace:
        result = orchestrator.handle_message(conversation_id=conversation_id, message=mensaje)
        trace_output = tracing.build_root_output(result)
        trace.update(output=trace_output)

    # 3. Mostrar respuesta
    print("=" * 60)
    print("💬 RESPUESTA DEL ASISTENTE")
    print("=" * 60)
    print(f"Tipo: {result.type.value}")
    print(f"Mensaje: {result.message}\n")
    print("Fuentes citadas:")
    for s in result.sources:
        print(f"  - [{s.kind}] {s.reference}: {s.title}")

    # 4. Mostrar árbol de observaciones de Langfuse
    print("\n" + "=" * 60)
    print("📊 ÁRBOL DE OBSERVACIONES REGISTRADAS EN LANGFUSE")
    print("=" * 60)
    print(f"Trace raíz: chat_turn [span] (session_id = {conversation_id})")

    for obs in mock_client.observations:
        if obs.name == "chat_turn":
            continue
        as_type = obs.as_type.upper()
        name = obs.name

        details = []
        if obs.kwargs.get("metadata"):
            for k, v in obs.kwargs["metadata"].items():
                details.append(f"{k}={v}")

        for u in obs.updates:
            out = u.get("output")
            if isinstance(out, dict):
                if "intent" in out:
                    details.append(f"intent={out['intent']}")
                if "resolved" in out:
                    details.append(f"resolved={out['resolved']}")
                if "count" in out:
                    details.append(f"rules_count={out['count']}")
                if "citations" in out:
                    details.append(f"citations={out['citations']}")
                if "fallback_used" in out:
                    details.append(f"fallback_used={out['fallback_used']}")
            elif out is not None:
                details.append(f"output={out}")

        detail_str = f" ({', '.join(details)})" if details else ""
        print(f"  ├── [{as_type:10}] {name}{detail_str}")

    print("=" * 60)
    print("✅ Demostración completada sin errores.")
    print("=" * 60)


if __name__ == "__main__":
    run_demo()
