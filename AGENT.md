# AGENT.MD — CONTRATO DE ALCANCE Y ARQUITECTURA CONGELADA

> ⚠️ **REGLA DE ORO DE DESARROLLO**:
> El alcance y la arquitectura de este proyecto están **100% CONGELADOS**.
> Queda **estrictamente prohibido** que cualquier agente de IA o desarrollador introduzca nuevos servicios en la nube, añada más agentes, cree bases de datos adicionales o complique el diseño.
> El foco absoluto es: **código limpio, 100% testeado, documentado y defendible en entrevista técnica**.

---

## 1. Matriz de Decisiones Arquitectónicas (FROZEN STACK)

Cualquier cambio a esta tabla se considera una violación del alcance del proyecto.

| Componente | Tecnología Seleccionada | Justificación / Restricción |
| :--- | :--- | :--- |
| **Frontend Demo** | **Streamlit** | UI rápida, interactiva y limpia para demostración inmediata al cliente. |
| **Backend API** | **FastAPI** | Framework asíncrono en Python, tipado estricto con Pydantic y endpoints limpios (/health, /api/chat). |
| **Orquestador** | **1 Único Router (Intent Router)** | Clasificador determinista de 4 vías. **PROHIBIDO crear 5-6 sub-agentes**. |
| **LLM** | **Azure OpenAI** | gpt-4o (razonamiento de combate) y gpt-4o-mini (clasificación/extracción). Fallback transparente a OpenAI/Mock para tests. |
| **Vector DB / RAG** | **PostgreSQL + pgvector** | Almacenamiento unificado de embeddings con índice HNSW (`vector_cosine_ops`) y Full Text Search (`tsvector`). **PROHIBIDO Azure AI Search**. |
| **Herramienta Externa** | **MTG REST API** | Consumo directo de `https://api.magicthegathering.io/v1/cards` con `User-Agent` personalizado y mapeo de filtros. |
| **Memoria Conversacional** | **PostgreSQL** | Persistencia de sesiones y acumulación de filtros en tablas relacionales. **PROHIBIDO Cosmos DB**. |
| **Entorno Local** | **Docker Compose** | Imagen oficial `pgvector/pgvector:pg16` para base de datos local en puerto 5432. |
| **Cloud Provider** | **Microsoft Azure** | Despliegue productivo en Azure Container Apps + PostgreSQL Flexible Server. |
| **IaC (Infraestructura)** | **Terraform** | Código modular en `infra/terraform/` validado (`terraform validate`). **PROHIBIDO Bicep / ARM redundantes**. |
| **Observabilidad** | **Application Insights / OpenTelemetry** | Trazabilidad distribuida APM, percentiles de latencia (p95), errores y auditoría de tokens. |

---

## 2. Los Únicos 4 Flujos Permitidos

No se implementará ni evaluará ningún flujo fuera de estos cuatro:

### Flujo 1: Rules RAG
* **Entrada**: Dudas de reglamento (*"¿Cómo funciona el maná?"*, *"¿Qué fases hay en un turno?"*, o interacción de combate *"Rapaz del campo de batalla [Dañar primero] + Ninja de horas tardías [Ninjutsu]"*).
* **Proceso**: Recuperación híbrida sobre data/official_rules_mtg.json / PostgreSQL pgvector.
* **Salida Obligatoria**: Respuesta fundamentada + **Citación explícita de fuentes** (Magic Comprehensive Rules (CR XXX.X)).

### Flujo 2: Card Search (Tool Calling Estructurado)
* **Entrada**: Consulta en lenguaje natural (*"Busco una carta blanca de coste inferior a dos de mana que sea guerrero"*).
* **Proceso**: Extracción de entidades a parámetros tipados (colorIdentity=W, subtypes=Warrior, cmc<=1), llamada HTTP a la API de MTG.
* **Salida Obligatoria**: Listado de cartas con nombre, coste, tipo e imagen oficial de Gatherer (imageUrl).

### Flujo 3: Multi-turn Conversation (Contexto Acumulativo)
* **Entrada**: Pregunta elíptica tras una búsqueda previa (*"¿Y alguna que cueste solo uno?"*).
* **Proceso**: El gestor de memoria recupera el estado last_card_filter de la sesión y fusiona las restricciones (color=W, subtype=Warrior, cmc=1).
* **Salida Obligatoria**: Resultados filtrados demostrando que el asistente no perdió el contexto previo.

### Flujo 4: Custom Card [Bonus]
* **Entrada**: Petición de diseño (*"Quiero una carta de Han Solo, blanca-roja que tenga dañar primero"*).
* **Proceso**: Síntesis de diseño respetando las directrices oficiales de Wizards of the Coast (*Color Pie*).
* **Salida Obligatoria**: Ficha estructurada de la carta con coste, tipo, estadísticas (3/2), habilidad coherente y texto de ambientación (*Flavor Text*).

---

## 3. Servicios Estrictamente Prohibidos (Anti-Sobreingeniería)

Para evitar preguntas trampa o acusaciones de sobreingeniería en la revisión técnica:
* ❌ **NO usar 6 agentes** (se usa exactamente 1 Router).
* ❌ **NO usar Azure AI Search** (se usa PostgreSQL con pgvector).
* ❌ **NO usar Azure Cosmos DB** (se usa PostgreSQL para sesiones y memoria).
* ❌ **NO usar Redis** (la caché se gestiona en PostgreSQL / memoria).
* ❌ **NO añadir LangGraph con decenas de nodos** si un Router limpio en Python resuelve los 4 flujos.

---

## 4. Definición de Terminado (Definition of Done — DoD)

Una tarea solo se considera terminada si cumple:
1. **Alcance**: Pertenece estrictamente a los 4 flujos permitidos.
2. **Código Limpio**: Python con tipado estricto (Pydantic / Type Hints), sin código muerto ni dependencias innecesarias.
3. **Tests**: Pasa con éxito la suite de pruebas unitarias (pytest tests/ -v) con 100% de éxito.
4. **Offline Resilience**: El sistema funciona tanto con Azure OpenAI configurado como en modo determinista local para pruebas sin saldo.
5. **Documentado**: Toda decisión de arquitectura está reflejada en README.md y en el documento de arquitectura productiva.
