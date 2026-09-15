# MTG Call Center AI Assistant
**Asistente de Soporte y Juez de Reglas para Magic: The Gathering en Microsoft Azure**

---

## 🚀 Enlaces Directos del Despliegue en Producción (Cloud)

La solución se encuentra completamente desplegada y operativa en la nube de **Microsoft Azure** (Región: `swedencentral`):

* 🌐 **Aplicación Web Desplegada (Chat en Vivo)**:  
  👉 [**https://mtg-assistant-app.ashyisland-b6708f09.swedencentral.azurecontainerapps.io/chat/**](https://mtg-assistant-app.ashyisland-b6708f09.swedencentral.azurecontainerapps.io/chat/)  
  *(Interfaz web conversacional NLUX consumiendo la API de FastAPI sobre Azure Container Apps)*

* 📑 **Documentación Interactiva de la API (Swagger UI)**:  
  👉 [**https://mtg-assistant-app.ashyisland-b6708f09.swedencentral.azurecontainerapps.io/docs**](https://mtg-assistant-app.ashyisland-b6708f09.swedencentral.azurecontainerapps.io/docs)

* 🔭 **Observabilidad de IA en Producción (Langfuse Cloud v4)**:  
  👉 [**https://cloud.langfuse.com**](https://cloud.langfuse.com)  
  *(Trazas distribuidas `chat_turn`, spans de clasificación, herramientas, recuperación vectorial RAG, modelos `gpt-4o`, métricas de tokens, latencias y costes)*

* 🏛️ **Diagrama de Arquitectura Interactivo (Archify Showcase)**:  
  👉 [**`docs/architecture.html`**](docs/architecture.html)  
  *(Diagrama interactivo autónomo con selector de temas claro/oscuro, vistas guiadas, trace motion y exportación PNG/SVG/WebM, validado con 9/9 comprobaciones superadas)*

* 🩺 **Probes de Salud y Disponibilidad del Contenedor**:  
  - **Liveness Probe**: [https://mtg-assistant-app.ashyisland-b6708f09.swedencentral.azurecontainerapps.io/health](https://mtg-assistant-app.ashyisland-b6708f09.swedencentral.azurecontainerapps.io/health)  
  - **Readiness Probe**: [https://mtg-assistant-app.ashyisland-b6708f09.swedencentral.azurecontainerapps.io/ready](https://mtg-assistant-app.ashyisland-b6708f09.swedencentral.azurecontainerapps.io/ready) *(valida conexión activa a PostgreSQL 16 y extensión VECTOR)*

---

## 🎯 Los 4 Flujos del Reto

1. **Flujo 1 — Rules RAG & Combat Reasoning**:
   - Resuelve dudas sobre maná (CR 106), fases del turno (CR 500) y puzzles complejos de combate (*Rapaz del campo de batalla [Dañar primero] + Ninja de horas tardías [Ninjutsu]*).
   - Ejecutado por el **Rules Reasoning Agent** aplicando *Chain-of-Thought (CoT)* sobre las Comprehensive Rules y el texto Oracle oficial.
   - Devuelve `type: "rules"` con citas estructuradas obligatorias en `sources` (`CR 106.1`, `CR 702.48c`, `CR 702.7b`, etc.).

2. **Flujo 2 — Card Search (Tool Calling Estructurado)**:
   - Traduce lenguaje natural (*"Busco una carta blanca guerrero de coste inferior a dos"*).
   - Extrae entidades y normaliza filtros canónicos (`color: "W"`, `subtype: "Warrior"`, `max_cmc: 1` corrigiendo la anomalía de igualdad estricta de la API externa).
   - Devuelve `type: "card_search"`, lista de cartas con enlaces oficiales a Gatherer y `active_filters`.

3. **Flujo 3 — Multi-turn Conversation (Contexto Acumulativo)**:
   - Preserva y fusiona filtros entre turnos conversacionales mediante `ConversationMemory`.
   - Si tras el Flujo 2 el usuario pregunta *"¿Y alguna que cueste solo uno?"*, el sistema mantiene `color="W"` y `subtype="Warrior"` y actualiza `cmc=1`.

4. **Flujo 4 — Custom Card [Bonus]**:
   - Genera diseño estructurado y balanceado según la filosofía oficial del *Color Pie* de Wizards of the Coast (ej. *Han Solo, Capitán del Halcón 3/2, Boros {1}{R}{W} con Dañar primero*).
   - Localización estricta consistente con la aplicación (español por defecto con terminología canónica oficial de Magic: *Dañar primero, Prisa, Volar*, etc.).
   - La metadata visual `art_prompt` se preserva internamente para una futura etapa de generación artística y nunca se expone al usuario ni en la interfaz.
   - No genera todavía arte visual o renders gráficos (product gap conocido en desarrollo); `image_url: null` es un diseño intencionado y honesto para no fabricar URLs ni alucinar assets inexistentes.

---

## 🏛️ Arquitectura Productiva y Decisiones Técnicas

### Matriz de Decisiones Arquitectónicas

| Componente | Demo Local | Arquitectura Productiva Desplegada (Azure) |
| :--- | :--- | :--- |
| **Frontend** | Chat web NLUX (`src/ui/web`) servido por FastAPI | Desplegado en Azure Container Apps (`/chat/`) |
| **API** | FastAPI (`/api/chat`, `/health`, `/ready`) con Pydantic | Contenedor serverless escalable (1 a 3 réplicas) |
| **Orquestador** | Router determinista central (<10ms triage) | Router con instrumentación OpenTelemetry + Langfuse |
| **RAG / Reglas** | **PostgreSQL 16 + `pgvector` HNSW** + Fallback léxico | PostgreSQL Flexible Server v16 + `pgvector` (HNSW cosine) |
| **Cartas / Herramienta** | Tool HTTP (`magicthegathering.io`) con corrección `max_cmc` | Tool con caché en PostgreSQL (`mtg_card_cache` JSONB) |
| **Memoria** | Gestor contextual multi-turno relacional | Tabla relacional `chat_sessions` en PostgreSQL (**Sin Redis**) |
| **LLM** | Fallback determinista local sin internet | Azure OpenAI (`gpt-4o`, `gpt-4.1-mini`, `text-embedding-3-small`) |
| **Observabilidad AI** | **Langfuse v4** (`tracing.py` con trazas y spans) | Langfuse Cloud v4 + OpenTelemetry |
| **Observabilidad Infra** | Health endpoints y logging local | Azure Application Insights + Log Analytics Workspace |
| **IaC** | Terraform modular validado | Aprovisionamiento automatizado en `swedencentral` |
| **Seguridad** | Variables de entorno `.env` | User-Assigned Managed Identity + Azure Key Vault |

### Principios Anti-Sobreingeniería
- **Cero Redis**: Toda la memoria de sesión y la caché de cartas se gestionan de forma unificada en PostgreSQL 16 con tipos nativos JSONB e índices GIN.
- **Cero Azure AI Search / Cosmos DB**: Unificados en PostgreSQL + `pgvector` con indexación HNSW (`vector_cosine_ops`), reduciendo costes de infraestructura y eliminando puntos de fallo distribuido.
- **Cero enjambres de microagentes**: Las tareas mecánicas (búsqueda de cartas, extracción de entidades y formateo) son funciones deterministas y herramientas directas en Python.
- **Seguridad Zero-Trust**: La aplicación utiliza una Identidad Administrada Asignada por el Usuario (`mtg-assistant-ca-identity-40p02b`) para resolver secretos dinámicamente desde Azure Key Vault sin contraseñas en variables de entorno.

---

## 📄 Contrato de la API HTTP

La API se comunica a través de contratos estrictamente tipados con Pydantic.

### 1. `POST /api/chat`
Endpoint principal conversacional y de soporte.

#### Request Payload
```json
{
  "conversation_id": "session-123e4567-e89b-12d3-a456-426614174000",
  "message": "¿Qué ocurre si una criatura con Dañar primero ataca y activo Ninjutsu?"
}
```

#### Response Payload — Rules / Combat Interaction
```json
{
  "conversation_id": "session-123e4567-e89b-12d3-a456-426614174000",
  "type": "rules",
  "message": "En el paso de daño de dañar primero, la criatura atacante asigna su daño...",
  "cards": [
    {
      "name": "Battlefield Raptor",
      "mana_cost": "{W}",
      "cmc": 1.0,
      "type_line": "Creature — Bird",
      "oracle_text": "Flying, first strike",
      "image_url": "http://gatherer.wizards.com/Handlers/Image.ashx?multiverseid=503613&type=card",
      "set_name": "Kaldheim"
    }
  ],
  "sources": [
    {
      "kind": "rule",
      "title": "Comprehensive Rules",
      "reference": "CR 702.48c",
      "url": null
    },
    {
      "kind": "rule",
      "title": "Comprehensive Rules",
      "reference": "CR 702.7b",
      "url": null
    }
  ],
  "active_filters": null
}
```

#### Response Payload — Card Search
```json
{
  "conversation_id": "session-123e4567-e89b-12d3-a456-426614174000",
  "type": "card_search",
  "message": "He encontrado 4 cartas que cumplen tus criterios (color W, subtipo Warrior, coste <= 1).",
  "cards": [
    {
      "name": "Dragon Hunter",
      "mana_cost": "{W}",
      "cmc": 1.0,
      "type_line": "Creature — Human Warrior",
      "oracle_text": "Protection from Dragons...",
      "image_url": "http://gatherer.wizards.com/...",
      "set_name": "Dragons of Tarkir"
    }
  ],
  "sources": [
    {
      "kind": "external_api",
      "title": "Magic: The Gathering API",
      "reference": "cards",
      "url": "https://api.magicthegathering.io/v1/cards"
    }
  ],
  "active_filters": {
    "color": "W",
    "subtype": "Warrior",
    "card_type": null,
    "cmc": null,
    "max_cmc": 1
  }
}
```

### 2. `GET /health` (Liveness Probe)
Responde HTTP 200 inmediatamente si el proceso está activo:
```json
{
  "status": "healthy",
  "service": "MTG Call Center Assistant",
  "version": "1.0.0"
}
```

### 3. `GET /ready` (Readiness Probe)
Verifica conectividad activa con PostgreSQL y el estado de la extensión `VECTOR`:
```json
{
  "status": "ready",
  "database_reachable": true,
  "pgvector_ready": true,
  "rag_backend": "auto",
  "service": "MTG Call Center Assistant",
  "version": "1.0.0"
}
```

---

## 💻 Ejecución en Local (Modo Fallback / Desarrollo)

Si se desea ejecutar la solución en un entorno local para desarrollo, pruebas offline o evaluación técnica:

### 1. Iniciar PostgreSQL + pgvector con Docker
```bash
docker compose up -d
```
*Inicia la imagen oficial `pgvector/pgvector:pg16` en el puerto `5432` con usuario `mtg_admin`.*

### 2. Aplicar Esquema e Índices HNSW de Forma Idempotente
```bash
python scripts/apply_schema.py
```
*Crea la base de datos `mtg_callcenter_db`, activa la extensión `vector`, crea la tabla `mtg_rules` y construye el índice HNSW `mtg_rules_embedding_hnsw_idx` con operador de similitud de coseno `<=>`.*

### 3. Ingestar Reglas Canónicas y Generar Embeddings
```bash
python scripts/ingest_rules.py
```
*Ingesta idempotente con hashing SHA-256. Si no hay credenciales de Azure OpenAI configuradas en `.env`, las reglas quedan disponibles para el backend léxico de fallback sin bloquear la aplicación.*

### 4. Iniciar el Backend (FastAPI + Chat Web)
```bash
uvicorn src.api.app:app --reload --port 8000
```
- **Chat Web Interactivo**: [http://localhost:8000/chat/](http://localhost:8000/chat/)
- **Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Liveness Probe**: [http://localhost:8000/health](http://localhost:8000/health)
- **Readiness Probe**: [http://localhost:8000/ready](http://localhost:8000/ready)

### 5. Resiliencia de Backend RAG (`RAG_BACKEND=auto`)
- **`auto`**: Intenta primero la búsqueda vectorial semántica mediante `pgvector`. Si la base de datos no está levantada o los embeddings no están disponibles, conmuta automáticamente al **recuperador léxico canónico** sin interrumpir la experiencia de usuario.
- Para forzar un modo específico: configurar `RAG_BACKEND=pgvector` o `RAG_BACKEND=lexical` en `.env`.

---

## 🧪 Estrategia de Pruebas (Zero Internet Unit Tests)

El proyecto cuenta con una suite completa de pruebas estrictamente desacopladas para garantizar determinismo y velocidad:

* **Tests Unitarios (100% Offline, sin dependencias de red)**:
  ```bash
  pytest tests/unit -v
  ```
  *75 tests que validan los 5 escenarios de aceptación, el contrato API, los 4 flujos, multi-turno HTTP, pgvector RAG, resiliencia de fallback, embeddings mock y observabilidad en <5 segundos.*

* **Tests de Integración en Vivo**:
  ```bash
  pytest -m integration -v
  ```
  *Valida pgvector real contra PostgreSQL (operador `<=>` y cálculo de score) y la API externa de MTG.*

---

## 🔭 Observabilidad de IA con Langfuse y OpenTelemetry

El sistema incluye instrumentación con **Langfuse v4** (basado en OpenTelemetry).

### Variables de Entorno (`.env`)
Para activar el envío de trazas a Langfuse Cloud en local:
```env
LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_BASE_URL=https://cloud.langfuse.com
LANGFUSE_CAPTURE_CONTENT=true
APP_ENV=local
```
*Si `LANGFUSE_ENABLED=false` o no se configuran credenciales, el sistema opera automáticamente en **modo No-Op** sin generar llamadas de red ni excepciones.*

### Jerarquía de Trazas
Cada petición a `/api/chat` genera una traza raíz `chat_turn` agrupada bajo `session_id = conversation_id`:

```text
chat_turn                                  span (trace raíz)
│
├── route_intent                          span (router determinista <10ms)
│
├── extract_card_entities                 span (extracción sintáctica)
│
├── resolve_cards                         tool (validación con API MTG)
│    └── mtg_api_get_card                 tool
│
├── retrieve_rules                        retriever (backend=pgvector o fallback)
│
├── rules_reasoning_agent                 agent (Juez L3 CoT)
│    └── azure_openai_structured          generation (gpt-4o)
│
└── build_response                        span (ensamblaje AssistantResult)
```

**Privacidad & Seguridad de Telemetría**:
- `reasoning_steps`, `chain_of_thought` y reflexiones internas son redactadas automáticamente antes del envío.
- Claves de API (`sk-...`), contraseñas y URLs de bases de datos son filtradas por el sanitizador recursivo.
