# MTG Call Center AI Assistant

> 🧊 **ARQUITECTURA Y ALCANCE CONGELADOS**  
> Este proyecto sigue estrictamente el contrato establecido en [`AGENT.md`](AGENT.md).  
> **Objetivo**: Código limpio, 100% testeado, documentado y defendible en entrevista técnica. Cero sobreingeniería.

---

## 🏛️ Matriz de Decisiones Arquitectónicas Congeladas

| Componente | Tecnología Seleccionada | Justificación Técnica |
| :--- | :--- | :--- |
| **Frontend Demo** | **Streamlit** | Interfaz conversacional rápida, limpia e interactiva con visualización de cartas e imágenes. |
| **Backend API** | **FastAPI** | Framework asíncrono en Python, tipado estricto Pydantic y endpoints de producción (`/health`, `/api/chat`). |
| **Orquestador** | **1 Router (Intent Router)** | Clasificador determinista de 4 vías. Cero agentes superfluos ni bucles infinitos. |
| **LLM** | **Azure OpenAI** | `gpt-4o` (razonamiento complejo de combate) y `gpt-4o-mini` (extracción/enrutado). Fallback local determinista. |
| **Vector DB / RAG** | **PostgreSQL + pgvector** | Almacenamiento unificado de embeddings (HNSW `vector_cosine_ops`) y Full-Text Search (`tsvector`). Sustituye Azure AI Search a 1/10 del coste. |
| **Herramienta Externa** | **MTG REST API** | Integración con `https://api.magicthegathering.io/v1/cards` con `User-Agent` personalizado y mapeo español-inglés. |
| **Memoria Conversacional** | **PostgreSQL** | Persistencia de sesiones y acumulación elíptica de filtros. Sustituye Cosmos DB. |
| **Entorno Local** | **Docker Compose** | Imagen oficial `pgvector/pgvector:pg16` para base de datos local en puerto 5432. |
| **Cloud Provider** | **Microsoft Azure** | Despliegue en Azure Container Apps + PostgreSQL Flexible Server. |
| **IaC (Infraestructura)** | **Terraform** | Código modular en `infra/terraform/` validado con `terraform validate` (0 errores, 0 warnings). |
| **Observabilidad** | **Application Insights / OpenTelemetry** | Trazabilidad distribuida APM, percentiles de latencia (p95), errores y auditoría de tokens. |

---

## 🎯 Los 4 Únicos Flujos del Reto

1. **Flujo 1 — Rules RAG**:
   - Resuelve dudas sobre el maná (CR 106), fases del turno (CR 500) y puzzles de combate (*Rapaz del campo de batalla [Dañar primero] + Ninja de horas tardías [Ninjutsu]*).
   - Incluye citas formales: `Magic Comprehensive Rules (CR XXX.X)`.
2. **Flujo 2 — Card Search (Tool Calling)**:
   - Traduce lenguaje natural (*"Busco una carta blanca de coste inferior a dos que sea guerrero"*) a filtros tipados sobre la API REST oficial, devolviendo nombres, costes, tipos e imágenes oficiales de Gatherer.
3. **Flujo 3 — Multi-turn Conversation**:
   - Preserva el contexto de filtros. Tras la búsqueda anterior, si el usuario pregunta: *"¿Y alguna que cueste solo uno?"*, el sistema acumula las restricciones (`color=blanco, subtype=guerrero, cmc=1`).
4. **Flujo 4 — Custom Card [Bonus]**:
   - Diseña cartas equilibradas según el *Color Pie* (ej. *"Quiero una carta de Han Solo, blanca-roja con dañar primero"*).

---

## 📋 Definition of Done (DoD)

- [x] **Arquitectura y Alcance Congelados**: Registrado contractualmente en `AGENT.md`.
- [x] **Los 4 Flujos Implementados**: RAG, Tool Search, Multi-turno y Custom Card.
- [x] **Tests Automatizados**: 9 tests con `pytest` pasando con 100% de éxito (`pytest tests/ -v`).
- [x] **Frontend Demo**: Streamlit (`app_streamlit.py`) y chat web embebido en FastAPI (`/`).
- [x] **Docker Compose**: Configurado con `pgvector/pgvector:pg16` para entorno local.
- [x] **Terraform Validado**: Infraestructura Azure en `infra/terraform/` (`terraform validate`).
- [x] **Documento Productivo**: Entregable Word de 15 puntos en [`docs/Solucion_Productiva_MTG_CallCenter.docx`](docs/Solucion_Productiva_MTG_CallCenter.docx).

---

## 🚀 Cómo Ejecutar la Solución

### 1. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 2. Ejecutar la Demo Frontend (Streamlit)
```bash
streamlit run app_streamlit.py
```
Abre en tu navegador la UI interactiva con botones rápidos para cada uno de los 4 flujos y renderizado de cartas.

### 3. (Alternativa) Ejecutar el Backend FastAPI
```bash
uvicorn src.api.app:app --reload --port 8000
```
- API Docs interactiva: `http://localhost:8000/docs`
- Health Check: `http://localhost:8000/health`
- Web Chat integrado: `http://localhost:8000/`

### 4. Ejecutar la Batería de Pruebas (Pytest)
```bash
pytest tests/ -v
```

### 5. Levantar PostgreSQL + pgvector local (Docker)
```bash
docker compose up -d
```

### 6. Validar Infraestructura Cloud (Terraform)
```bash
cd infra/terraform
terraform validate
```
