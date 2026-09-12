# MTG Call Center AI Assistant

Asistente de soporte especializado para jugadores y operadores de Call Center de **Magic: The Gathering (MTG)**.
Diseñado bajo una filosofía pragmática, limpia y comprobada: **FastAPI + RAG (PostgreSQL/pgvector) + MTG API + Pytest + Docker + Terraform (Azure)**.

---

## 🎯 Los 3 Casos de Uso Clave (100% Funcionales)

1. **Caso A — RAG de Reglas Canónicas**:
   - Resuelve dudas sobre el maná (CR 106), fases del turno (CR 500) y puzzles de combate (*Rapaz del campo de batalla [Dañar primero] + Ninja de horas tardías [Ninjutsu]*).
   - Incluye citas formales y citaciones: Magic Comprehensive Rules (CR XXX.X).
2. **Caso B — Tool Calling Estructurado**:
   - Traduce lenguaje natural (*"Busco una carta blanca de coste inferior a dos que sea guerrero"*) a filtros tipados sobre la API REST oficial (https://api.magicthegathering.io/v1/cards), devolviendo nombres, costes, tipos e imágenes oficiales de Gatherer.
3. **Caso C — Conversación Multi-turno**:
   - Preserva el contexto de filtros. Tras la búsqueda anterior, si el usuario pregunta: *"¿Y alguna que cueste solo uno?"*, el sistema acumula las restricciones (color=blanco, subtype=guerrero, cmc=1).
4. **Bonus — Creación de Cartas Custom**:
   - Diseña cartas equilibradas según el *Color Pie* (ej. *"Quiero una carta de Han Solo, blanca-roja con dañar primero"*).

---

## 🚀 Inicio Rápido en Local

### 1. Instalar dependencias
`ash
pip install -r requirements.txt
`

### 2. Ejecutar la Demo (FastAPI + Web Chat UI)
`ash
uvicorn src.api.app:app --reload --port 8000
`
Abre tu navegador en: **http://localhost:8000** para probar el chat interactivo con botones de consulta rápida y visualización de cartas.

### 3. Ejecutar la Batería de Pruebas (Pytest)
`ash
pytest tests/ -v
`
*9 tests unitarios e integración que validan el 100% de los requisitos (salud, RAG con citas, tool use, multi-turno, resiliencia ante errores de API externa).*

### 4. (Opcional) Levantar Base de Datos PostgreSQL + pgvector con Docker
`ash
docker compose up -d
`

---

## ☁️ Infraestructura Cloud en Azure (Terraform)

La arquitectura productiva en Azure está declarada y validada en infra/terraform/:
`ash
cd infra/terraform
terraform init
terraform validate
`
*Resultado: Success! The configuration is valid (0 errores, 0 advertencias).*

**Servicios aprovisionados**:
- **Azure Container Apps**: Backend serverless FastAPI auto-escalable.
- **Azure Database for PostgreSQL Flexible Server**: Extensión pgvector activada para búsqueda híbrida (HNSW + Full Text Search).
- **Azure OpenAI**: Modelos GPT-4o, GPT-4o-mini y embeddings text-embedding-3-large.
- **Azure Application Insights**: Trazabilidad distribuida APM (OpenTelemetry) y métricas de tokens/latencia.
- **Azure Key Vault**: Gestión de secretos mediante Managed Identity.

---

## 📄 Documentación Entregable

- **Documento Word Oficial**: [docs/Solucion_Productiva_MTG_CallCenter.docx](docs/Solucion_Productiva_MTG_CallCenter.docx) (Estructurado en los 15 puntos requeridos para la defensa técnica).
- **Documento Markdown con Diagramas**: [docs/architecture_production.md](docs/architecture_production.md).
