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
| **RAG / Reglas** | **PostgreSQL 16 + `pgvector` HNSW** (1536d) + Fallback Léxico resiliente | PostgreSQL Flexible Server + `pgvector` HNSW |
| **Cartas** | Tool HTTP (`magicthegathering.io`) con bug `max_cmc` corregido | Tool con caché en PostgreSQL |
| **Memoria** | Gestor contextual multi-turno (repreguntas elípticas) | Tabla relacional en PostgreSQL |
| **LLM** | Motor de síntesis determinista con fallback | Azure OpenAI (`gpt-4o` y `gpt-4o-mini`) (Milestone 3) |
| **Observabilidad AI** | **Langfuse v4** (`tracing.py` con trazas de chat, RAG, agents, tools y fallback) | Langfuse Cloud + OpenTelemetry |
| **Observabilidad Infra** | Health endpoints y logging local | Azure Application Insights (propuesta APM) |
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

## 🏛️ RAG con PostgreSQL + pgvector (HNSW)

El sistema de reglas oficiales (`mtg_rules`) implementa recuperación vectorial con fallback determinista:

```text
               INGESTIÓN IDEMPOTENTE
             official_rules_mtg.json
                        │
                        ▼
               load_rule_chunks()
                        │
                        ▼
             calculate_content_hash()
              (SHA256 idempotencia)
                        │
                        ▼
          Azure OpenAI EmbeddingService
             (text-embedding-3-small)
                        │
                        ▼
             PostgreSQL 16 + pgvector
        mtg_rules.embedding (HNSW cosine)


                    RUNTIME
              Pregunta del usuario
                        │
                        ▼
                 embed_query()
                        │
                        ▼
             PostgreSQL + pgvector
      1 - (embedding <=> query) AS score
                        │
                        ▼
                top-k RuleChunks
                        │
                        ▼
               RulesReasoningAgent
                        │
                        ▼
             Respuesta + Citas CR
```

**Resiliencia de Backend (`RAG_BACKEND=auto`)**:
- Si PostgreSQL o Azure OpenAI no están disponibles, el sistema degrada automáticamente a **recuperación léxica canónica** sin interrumpir el servicio.
- Si se requiere forzar un modo: `RAG_BACKEND=pgvector` o `RAG_BACKEND=lexical`.

### Comandos de Ingestión y Migración

1. **Iniciar PostgreSQL + pgvector con Docker**:
   ```bash
   docker compose up -d
   ```

2. **Aplicar Esquema e Índices HNSW de forma idempotente**:
   ```bash
   python scripts/apply_schema.py
   ```

3. **Ingestar Reglas Canónicas y Generar Embeddings**:
   ```bash
   python scripts/ingest_rules.py
   ```
   *Salida esperada (idempotente)*:
   ```text
   Rules loaded:       17
   New embeddings:     17 (o 0 si ya existen)
   Updated:            0
   Skipped unchanged:  0 (o 17 en ejecuciones sucesivas)
   ```

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
  *68 tests que validan los 5 escenarios de aceptación, contrato API, los 4 flujos, multi-turno HTTP, pgvector RAG, resiliencia de fallback, embeddings mock y observabilidad en <2 segundos.*

* **Tests de Integración en Vivo**:
  ```bash
  pytest -m integration -v
  ```
  *Valida pgvector real contra PostgreSQL (operador `<=>` y cálculo de score) y la API externa de MTG.*


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

---

## 🔭 Observabilidad de IA con Langfuse

El sistema incluye instrumentación con **Langfuse v4** (basado en OpenTelemetry).

### Variables de Entorno (`.env`)

Para activar el envío de trazas a Langfuse Cloud:

```env
LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_BASE_URL=https://cloud.langfuse.com
LANGFUSE_CAPTURE_CONTENT=true
APP_ENV=local
```

Si `LANGFUSE_ENABLED=false` o no se configuran credenciales, el sistema opera automáticamente en **modo No-Op** sin generar peticiones de red ni excepciones.

### Jerarquía de Trazas

Cada petición a `/api/chat` genera una traza `chat_turn` agrupada bajo `session_id = conversation_id`:

```text
chat_turn                                  span
│
├── route_intent                          span
│
├── extract_card_entities                 span
│
├── resolve_cards                         tool
│    └── mtg_api_get_card                 tool
│
├── retrieve_rules                        retriever (backend=lexical_fallback)
│
├── rules_reasoning_agent                 agent
│    └── azure_openai_structured          generation (o deterministic_fallback)
│
└── build_response                        span
```

**Privacidad & Seguridad**:
- `reasoning_steps`, `chain_of_thought` y reflexiones internas son eliminadas antes de enviar telemetría.
- Secretos, API keys (`sk-...`), contraseñas y URLs de bases de datos son redactados automáticamente.
