# MTG AI Challenge — Senior Implementation Plan

# 🎯 Objetivo

Construir una demo funcional y defendible con enfoque **senior**: primero una vertical slice completa y testeada, luego UI, infraestructura, observabilidad y documentación.

> **Principio rector:** cada ejecución debe dejar el sistema en un estado funcional.
> 

---

# 🧭 Arquitectura congelada

| Capa | Decisión |
| --- | --- |
| Frontend demo | Chat web NLUX |
| API | FastAPI |
| Orquestación | 1 router |
| LLM | Azure OpenAI |
| RAG | PostgreSQL + pgvector |
| Herramienta externa | MTG API |
| Memoria | PostgreSQL |
| Entorno local | Docker Compose |
| Cloud | Azure |
| IaC | Terraform |
| Monitoring | Application Insights / OpenTelemetry |

## Flujos incluidos

1. **Rules RAG**
2. **Card Search**
3. **Multi-turn Conversation**
4. **Custom Card** — bonus

**Definition of Done:** arquitectura congelada y README con estas decisiones.

---

# 1. Congelar alcance y arquitectura

No empezar desplegando Azure. Para un reto de un día, hacerlo demasiado pronto puede consumir tiempo en permisos, SKUs, regiones o Terraform antes de saber siquiera si la aplicación funciona.

La prioridad es construir primero una **vertical slice funcional**, asegurar contratos y tests, y después envolverla con UI, infraestructura y observabilidad.

---

# 2. Definir primero el contrato del backend

Antes de terminar la implementación, cerrar qué recibe y devuelve `/api/chat`.

## Request

```json
POST /api/chat

{
  "conversation_id": "abc123",
  "message": "Busco un guerrero blanco de coste inferior a 2"
}
```

## Response — Card Search

```json
{
  "conversation_id": "abc123",
  "type": "card_search",
  "message": "He encontrado estas cartas.",
  "cards": [
    {
      "name": "Dragon Hunter",
      "mana_cost": "{W}",
      "type": "Creature — Human Warrior",
      "image_url": "https://..."
    }
  ],
  "sources": []
}
```

## Response — Rules RAG

```json
{
  "type": "rules",
  "message": "El maná...",
  "cards": [],
  "sources": [
    {
      "title": "Comprehensive Rules",
      "reference": "CR 106.1"
    }
  ]
}
```

## Razón

Con el contrato cerrado:

```
UI
 │
 │ contrato conocido
 ▼
FastAPI
 │
 ▼
services
```

Se puede cambiar la implementación interna sin romper el frontend.

---

# 3. Construir primero el núcleo sin Azure

La aplicación debe funcionar **localmente** antes de añadir infraestructura.

## Estructura inicial

```
src/
├── tools/
│   └── mtg_api.py
├── services/
│   ├── rules_rag.py
│   └── memory.py
└── orchestrator.py
```

## Primer objetivo funcional

```python
result = assistant.chat(
    conversation_id="test",
    message="Busco una carta blanca guerrero de coste menor a dos"
)
```

Debe devolver un objeto correcto.

### Todavía no

- Chat web NLUX
- Azure Container Apps
- Terraform deploy
- UI bonita

Solo lógica.

## Tests simultáneamente

```
MTG API
  ↓
tests pass

RAG
  ↓
tests pass

Router
  ↓
tests pass

Memory
  ↓
tests pass
```

No implementar todo y dejar los tests para el final.

---

# 4. Vertical Slice 1 — Card Search

Es la primera porque es visual y valida varias capacidades de una vez.

## Flujo

```
Natural language
      ↓
structured extraction
      ↓
MTG API
      ↓
normalised objects
      ↓
images
```

### Entrada

> Busco una carta blanca guerrero de coste inferior a dos.
> 

### Resultado esperado

```
Dragon Hunter
White
Warrior
{W}
image_url
```

### Test

```
test_search_cards_under_two_mana
```

### Commit

```bash
git add .
git commit -m "feat: implement structured MTG card search"
```

---

# 5. Vertical Slice 2 — RAG

## Flujo

```
Question
   ↓
embedding
   ↓
pgvector
   ↓
top-k rules
   ↓
LLM
   ↓
answer + citations
```

No complicar el ingestion pipeline.

Para la demo:

```
document
 ↓
chunks
 ↓
embeddings
 ↓
Postgres
```

## Tests

```
test_rule_retrieval()
test_rule_retrieval_returns_sources()
```

## Commit

```bash
git commit -m "feat: add grounded rules RAG with citations"
```

---

# 6. Vertical Slice 3 — Memory

## Ejemplo

```
USER
"Quiero un guerrero blanco"

BOT
[...]

USER
"¿Y alguno que cueste uno?"
```

Debe mantener contexto:

```json
{
  "colour": "white",
  "subtype": "warrior",
  "cmc": 1
}
```

Esto demuestra que no es simplemente un buscador.

### Test

```
test_chat_preserves_context
```

Después, commit.

---

# 7. Exponer el núcleo con FastAPI

FastAPI se añade cuando la lógica ya funciona. Aquí no debería construirse lógica nueva.

## Responsabilidad

```
HTTP
 ↓
validation
 ↓
orchestrator.chat()
 ↓
response
```

## Endpoints suficientes

```
GET  /health
POST /api/chat
POST /api/conversations
```

`/api/conversations` puede ser opcional.

## Checkpoint

```bash
curl http://localhost:8000/health
```

Debe devolver:

```json
{
  "status": "ok"
}
```

Y `POST /api/chat` debe funcionar correctamente.

---

# 8. Chat web después del backend

La UI en src/ui/web/ no contiene inteligencia; consume POST /api/chat mediante fetch y renderiza con NLUX. FastAPI sirve el chat en /chat/.

El request contiene conversation_id y message. Cada respuesta muestra su texto y sus cartas dentro del mismo chat, con imágenes cuando existe image_url. Las referencias quedan en el desplegable Fuentes.

La separación permite cambiar la interfaz sin modificar el contrato HTTP.

---

# 9. Dockerización local

Cuando backend + UI funcionan, añadir:

```
docker-compose.yml
```

Servicios:

```
postgres + pgvector
backend
frontend
```

## Checkpoint

```bash
docker compose up --build
```

El objetivo real:

```
git clone
   ↓
docker compose up
   ↓
localhost
   ↓
demo funciona
```

---

# 10. Terraform

Terraform entra **después** de que la aplicación funcione localmente.

## Mapping local → Azure

| Local | Azure |
| --- | --- |
| Docker backend | Azure Container Apps |
| Postgres pgvector | PostgreSQL Flexible Server |
| .env | Key Vault |
| logs | Application Insights |
| OpenAI | Azure OpenAI |

## Estructura

```
infra/
└── terraform/
    ├── providers.tf
    ├── main.tf
    ├── variables.tf
    ├── outputs.tf
    └── terraform.tfvars.example
```

## Validación

```bash
terraform fmt
terraform init
terraform validate
terraform plan
```

> **Terraform válido ≠ despliegue obligatorio.**
> 

Si el tiempo aprieta:

```
terraform validate ✅
terraform plan ✅

deployment real → optional
```

Es mejor entregar una aplicación local sólida y Terraform correcto que una aplicación rota en Azure.

---

# 11. Despliegue en Azure

Solo después de tener todo lo anterior funcionando.

## Orden

```
1. Resource Group
2. Key Vault
3. PostgreSQL
4. Azure OpenAI / existing model
5. Application Insights
6. Container Apps Environment
7. Backend Container App
8. Frontend Container App
```

Dependencia principal:

```
DATABASE
   ↓
BACKEND
   ↓
FRONTEND
```

No desplegar la UI primero.

---

# 12. Observabilidad

No hace falta sobredimensionarla. Registrar lo necesario para explicar rendimiento y comportamiento.

## Campos recomendados

```
request_id
conversation_id
intent
tool_called
retrieval_latency_ms
llm_latency_ms
total_latency_ms
tokens_in
tokens_out
status
```

## Ejemplo

```
request_id=7af3
intent=CARD_SEARCH
tool=mtg_api
tool_latency=384ms
llm_latency=721ms
total=1107ms
status=200
```

---

# 13. Documento Word

No dejarlo completamente para el final.

Mientras se desarrolla, ir anotando las decisiones. Al final, sincronizar la documentación con lo que **realmente existe**.

## Regla

No documentar como implementado algo que no se construyó.

Separar claramente:

```
Demo implementation
```

de:

```
Recommended production architecture
```

Esto evita exagerar el alcance real.

---

# 14. Prueba end-to-end final

La última ejecución debe replicar exactamente lo que hará el entrevistador.

## Scenario 1 — Rules RAG

```
¿Cómo funciona el maná?
```

Comprobar:

- [ ]  respuesta
- [ ]  source CR
- [ ]  logs

## Scenario 2 — Card Search

```
Busco una carta blanca guerrero que cueste menos de dos.
```

Comprobar:

- [ ]  tool call
- [ ]  filtros
- [ ]  cartas
- [ ]  imágenes

## Scenario 3 — Memory

```
¿Y alguna que cueste exactamente uno?
```

Comprobar:

- [ ]  conserva contexto
- [ ]  no pide color otra vez

## Scenario 4 — RAG complejo

```
¿Cómo interactúan First Strike y Ninjutsu?
```

Comprobar:

- [ ]  retrieval
- [ ]  respuesta fundamentada
- [ ]  citations

## Scenario 5 — Bonus

```
Créame una carta de Han Solo blanca-roja.
```

---

# 15. Orden real de ejecución

## ❌ Evitar

```
Terraform
→ Azure
→ UI
→ backend
→ tests
```

## ✅ Seguir

```
1. Requirements / architecture
        ↓
2. API contracts
        ↓
3. Domain/services
        ↓
4. MTG tool
        ↓
5. RAG
        ↓
6. Memory
        ↓
7. Tests
        ↓
8. FastAPI
        ↓
9. Chat web NLUX
        ↓
10. Docker
        ↓
11. Terraform
        ↓
12. Azure deployment
        ↓
13. Monitoring
        ↓
14. Documentation
        ↓
15. End-to-end demo
```

---

# 🤖 Cómo trabajar con el agente de IA

No pedir:

> “Implementa todo el proyecto.”
> 

Dar tareas independientes y verificables.

## Ejecución 1

```
Implement card search.
Run tests.
Fix failures.
Stop.
```

## Ejecución 2

```
Implement RAG.
Run existing + new tests.
Fix regressions.
Stop.
```

## Ejecución 3

```
Implement conversation memory.
Run complete test suite.
Stop.
```

Esto reduce el riesgo de que el agente toque demasiados archivos, rompa varias cosas a la vez y dificulte rastrear qué cambio produjo un fallo.

---

# ✅ Regla de oro

> **Cada ejecución debe dejar el sistema en un estado funcional.**
> 

El objetivo no es enseñar la mayor cantidad posible de tecnología. El objetivo es demostrar **criterio de ingeniería, ejecución incremental, contratos claros, tests, separación de responsabilidades y capacidad de llevar una solución de local a producción sin romperla**.