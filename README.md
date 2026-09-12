# MTG Call Center AI Assistant

> 🧊 **ARQUITECTURA Y ALCANCE CONGELADOS**  
> Este proyecto sigue estrictamente el contrato establecido en [`AGENT.md`](AGENT.md).  
> **Objetivo**: Código limpio, 100% testeado, documentado y defendible en entrevista técnica. Cero sobreingeniería.

---

## 📊 Estado Actual: Demo Implementada vs. Arquitectura Propuesta

Para total transparencia técnica, distinguimos lo **ejecutable hoy** de la **evolución productiva**:

| Componente | Demo Local Implementada (Milestone 1) | Arquitectura Productiva Propuesta (Azure) |
| :--- | :--- | :--- |
| **Frontend** | Streamlit (`src/ui/app_streamlit.py`) consumiendo HTTP | Streamlit / Consola Omnicanal Call Center |
| **API** | FastAPI (`/api/chat`, `/health`) con esquemas Pydantic tipados | Azure Container Apps (serverless escalable) |
| **Orquestador** | 1 Router clasificando los 4 flujos en `AssistantResult` | Router en contenedor con observabilidad OpenTelemetry |
| **RAG / Reglas** | Ingesta jerárquica canónica (CR 100-900) con citaciones formales | PostgreSQL Flexible Server + `pgvector` HNSW (Milestone 2) |
| **Cartas** | Tool HTTP (`magicthegathering.io`) con bug `max_cmc` corregido | Tool con caché en PostgreSQL |
| **Memoria** | Gestor contextual multi-turno (repreguntas elípticas) | Tabla relacional en PostgreSQL |
| **LLM** | Motor de síntesis determinista con fallback | Azure OpenAI (`gpt-4o` y `gpt-4o-mini`) (Milestone 3) |
| **IaC** | Terraform validado en `infra/terraform/` (`terraform validate`) | Despliegue automatizado en Azure |

---

## 🎯 Los 4 Flujos del Reto

1. **Flujo 1 — Rules RAG**:
   - Resuelve dudas sobre el maná (CR 106), fases del turno (CR 500) y puzzles de combate (*Rapaz del campo de batalla [Dañar primero] + Ninja de horas tardías [Ninjutsu]*).
   - Devuelve `type: "rules"` con citas estructuradas en `sources`: `CR 106.1`, `CR 702.48c`, `CR 702.7b`, etc.
2. **Flujo 2 — Card Search (Tool Calling)**:
   - Traduce lenguaje natural (*"Busco una carta blanca guerrero de coste inferior a dos"*).
   - Filtros canónicos normalizados (`color: "W"`, `subtype: "Warrior"`, `max_cmc: 1`).
   - Devuelve `type: "card_search"`, lista de cartas con enlaces oficiales a Gatherer y `active_filters`.
3. **Flujo 3 — Multi-turn Conversation**:
   - Preserva el contexto de filtros entre turnos. Si tras el Flujo 2 el usuario pregunta *"¿Y alguna que cueste solo uno?"*, el sistema mantiene `color="W"` y `subtype="Warrior"` y actualiza `cmc=1`.
4. **Flujo 4 — Custom Card [Bonus]**:
   - Diseña cartas equilibradas según el *Color Pie* (Han Solo, Capitán del Halcón 3/2, Boros {1}{R}{W} con Dañar primero).
   - `image_url: null` honesto sin inventar enlaces falsos.

---

## 📄 Contrato de la API

El contrato completo, esquemas Pydantic y ejemplos JSON se encuentran documentados en:  
👉 **[`docs/api_contract.md`](docs/api_contract.md)**

Ejemplo de llamada con `curl`:
```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"conversation_id": "test-session-1", "message": "Busco una carta blanca guerrero"}'
```

---

## 🧪 Estrategia de Pruebas (Zero Internet Unit Tests)

Las pruebas están estrictamente desacopladas para garantizar ejecuciones deterministas y rápidas:

* **Tests Unitarios (100% Offline, sin Internet)**:
  ```bash
  pytest
  # o explícitamente:
  pytest tests/unit -v
  ```
  *17 tests que validan el contrato API, los 4 flujos, multi-turno HTTP, corrección del bug `max_cmc` y memoria en <1 segundo.*

* **Tests de Integración en Vivo (API Real de MTG)**:
  ```bash
  pytest -m integration -v
  ```
  *Ejecuta llamadas reales contra `https://api.magicthegathering.io/v1/cards` para validar la conectividad externa.*

---

## 🚀 Cómo Iniciar la Solución en Local

### 1. Iniciar el Backend (FastAPI)
```bash
uvicorn src.api.app:app --reload --port 8000
```
- API Docs interactiva: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

### 2. Iniciar el Frontend (Streamlit)
En otra terminal:
```bash
streamlit run src/ui/app_streamlit.py
```
Abre en tu navegador `http://localhost:8501`. Streamlit consumirá FastAPI exclusivamente vía HTTP.
