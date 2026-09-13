# AGENT.MD — CONTRATO DE ALCANCE Y ARQUITECTURA CONGELADA

> 🎯 **PRINCIPIO RECTOR DE DISEÑO**:
> La arquitectura sigue un patrón **Router-Worker pragmático**:
> - **Router Determinista Central**: Triage rápido (<10ms) para clasificación de intención y ejecución directa de herramientas en tareas mecánicas (búsqueda de cartas, filtros, diálogo general).
> - **Agentes Especializados donde realmente aportan valor cognitivo**:
>   1. **Rules & Combat Reasoning Agent**: Aplica Chain-of-Thought (CoT) sobre las reglas oficiales canónicas recuperadas para resolver situaciones complejas de combate (ej. *Dañar primero + Ninjutsu*, capas, prioridad).
>   2. **Custom Card Designer Agent**: Síntesis creativa y balance de mecánicas evaluando directrices oficiales del *Color Pie* de Wizards of the Coast.
> - **Anti-sobreingeniería**: Se prohíbe crear enjambres innecesarios de 5 o 6 micro-agentes para tareas que se resuelven con funciones deterministas y herramientas.
> - **Cero contradicciones en infraestructura**: La base de datos es **PostgreSQL + pgvector** (vectores HNSW, Full Text Search, sesiones y caché JSONB). **No se utiliza Redis ni bases de datos satélite**.

---

## 1. Matriz de Decisiones Arquitectónicas (FROZEN STACK)

| Componente | Tecnología Seleccionada | Justificación y Fronteras |
| :--- | :--- | :--- |
| **Frontend Demo** | **Streamlit** | `src/ui/app_streamlit.py` consumiendo FastAPI exclusivamente vía HTTP/JSON (`api_client.py`). |
| **Backend API** | **FastAPI** | `src/api/app.py` como capa HTTP fina. Tipado estricto con Pydantic (`schemas.py`), endpoints `/health` y `/api/chat`. |
| **Orquestación & Agentes** | **Router Determinista + Agentes Especializados** | Router central + **Rules Reasoning Agent** (resolución de combate) + **Custom Designer Agent** (diseño Color Pie). |
| **LLM** | **Azure OpenAI** | `gpt-4o` (razonamiento complejo de reglas y diseño custom) y `gpt-4o-mini` (extracción/clasificación). Fallback determinista local. |
| **Vector DB / RAG** | **PostgreSQL + pgvector** | Almacenamiento unificado de embeddings con índice HNSW (`vector_cosine_ops`) y Full Text Search (`tsvector`). Sustituye Azure AI Search. |
| **Herramienta Externa** | **MTG REST API** | `src/tools/mtg_api.py` consumiendo `https://api.magicthegathering.io/v1/cards` con `User-Agent` y corrección de `max_cmc`. |
| **Memoria y Caché** | **PostgreSQL** | Persistencia relacional de conversaciones (`chat_sessions`) y caché de cartas (`mtg_card_cache` en JSONB). **Sin Redis**. |
| **Entorno Local** | **Docker Compose** | Imagen oficial `pgvector/pgvector:pg16` para base de datos local en puerto 5432. |
| **Cloud Provider** | **Microsoft Azure** | Azure Container Apps + PostgreSQL Flexible Server con extensión `VECTOR`. |
| **IaC (Infraestructura)** | **Terraform** | Código modular en `infra/terraform/` validado (`terraform validate`, 0 errores). **Sin Redis ni Bicep**. |
| **Observabilidad** | **Application Insights / OpenTelemetry** | Trazabilidad distribuida APM, percentiles de latencia (p95), errores y auditoría de tokens. |

---

## 2. Los 4 Flujos Oficiales

1. **Flujo 1 — Rules RAG**:
   * *Entrada*: Consultas de reglas (maná CR 106, fases de turno CR 500) o interacción de combate (*Rapaz + Ninja*).
   * *Ejecutor*: RAG sobre reglas canónicas + **Rules Reasoning Agent**.
   * *Salida*: Explicación fundamentada + **Citaciones estructuradas obligatorias** (`SourceRef(kind='rule', reference='CR XXX.X')`).

2. **Flujo 2 — Card Search (Tool Calling Estructurado)**:
   * *Entrada*: Búsqueda en lenguaje natural (*"Busco una carta blanca guerrero de coste inferior a dos"*).
   * *Ejecutor*: Router determinista -> `MTGCardSearchTool` con filtros canónicos (`color='W'`, `subtype='Warrior'`, `max_cmc=1`).
   * *Salida*: Listado de cartas con nombre, coste, tipo e imagen oficial de Gatherer (`imageUrl`).

3. **Flujo 3 — Multi-turn Conversation (Contexto Acumulativo)**:
   * *Entrada*: Pregunta elíptica de refinamiento (*"¿Y alguna que cueste solo uno?"*).
   * *Ejecutor*: `ConversationMemory` fusiona filtros previos con la nueva restricción (`color='W'`, `subtype='Warrior'`, `cmc=1`).
   * *Salida*: Resultados precisos demostrando preservación del hilo conversacional a través de FastAPI.

4. **Flujo 4 — Custom Card [Bonus]**:
   * *Entrada*: Solicitud de carta ficticia (*"Quiero una carta de Han Solo, blanca-roja con dañar primero"*).
   * *Ejecutor*: **Custom Card Designer Agent** aplicando directrices del Color Pie.
   * *Salida*: Ficha estructurada (3/2, {1}{R}{W}, habilidades y flavor text) con `image_url: null` honesto.

---

## 3. Restricciones Anti-Sobreingeniería y Coherencia

* ❌ **NO usar Redis**: Toda la caché de cartas se gestiona de forma unificada en la tabla `mtg_card_cache` de PostgreSQL con columnas JSONB e índices GIN.
* ❌ **NO crear agentes para tareas mecánicas**: La búsqueda en la API de MTG, la extracción de filtros y el formateo de respuestas son tareas directas de herramientas, no requieren agentes autónomos.
* ❌ **NO usar Azure AI Search ni Cosmos DB**: Unificados en PostgreSQL + `pgvector`.

---

## 4. Definición de Terminado (Definition of Done — DoD)

1. **Contrato Único**: Streamlit consume FastAPI exclusivamente vía HTTP (`POST /api/chat`) con `conversation_id` UUID.
2. **Esquemas Tipados**: Modelos Pydantic en `src/api/schemas.py` (`ChatRequest`, `ChatResponse`, `SourceRef`, `CardResult`, `CardSearchFilters`).
3. **Cero Contradicciones**: Terraform, código, tests y documentación alineados (sin Redis, con PostgreSQL unificado).
4. **Tests 100% Deterministas**: Suite de tests unitarios pasa sin requerir Internet en <1 segundo.
5. **Documentación Clara**: Distinción explícita entre demo implementada y propuesta productiva cloud.
