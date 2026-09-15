# Code Review — Pipeline de ingesta y consulta RAG

## 1. Resumen ejecutivo

El fragmento funciona como una prueba de concepto mínima de RAG, pero no está listo para producción. Los problemas principales no son solo de estilo: hay riesgos de **seguridad**, **pérdida de datos**, **mala calidad de recuperación**, **fuga de información**, **coste/latencia innecesarios** y **falta de trazabilidad**.

La mejora propuesta mantiene el objetivo original ingestar documentos, generar embeddings, recuperar contexto y responder pero separa responsabilidades, saca secretos del código, persiste el vector store, añade chunking + metadata, usa IDs estables, procesa embeddings por lotes, controla la relevancia, limita el historial y valida las citas.

> Alcance importante: el código recibido trabaja con `list[str]`. No procesa directamente PDFs ni Word. Por tanto, una capa previa de parsing/OCR/layout debe convertir cada documento a texto fiable y adjuntar metadatos como fuente, página y versión. En un caso clínico esto es crítico, sobre todo para tablas de dosificación.

---

## 2. Problemas encontrados

### 2.1 Seguridad (Críticos)

| Problema | Impacto | Mejora |
|---|---|---|
| API key hardcodeada en el repositorio | Filtración de credenciales, abuso de cuota y obligación de rotación | Variable de entorno / secret manager. Nunca versionar claves reales |
| Contexto recuperado concatenado dentro del `system` prompt | Un documento malicioso podría contener instrucciones y convertirse en prompt injection | Mantener instrucciones separadas de evidencia; tratar el contenido recuperado explícitamente como datos |
| Historial persistido en `history.json` en texto plano | Riesgo de exponer conversaciones; especialmente grave si contienen PHI/PII | No persistir por defecto; usar almacenamiento controlado, cifrado, sesiones y política de retención |
| No existe frontera de datos sensibles | Si una pregunta contiene datos de paciente, el código los envía al proveedor LLM | Definir una capa de clasificación/gateway antes del LLM. Para el caso clínico, este RAG debe quedar limitado a contenido documental no-PHI |
| Sin validación de fuentes citadas | El modelo puede inventar referencias | Asignar IDs de fuente en backend y validar que las citas devueltas existan |

### 2.2 Bugs y robustez

| Problema | Impacto | Mejora |
|---|---|---|
| `create_collection("docs")` puede fallar si la colección ya existe | Reinicios no idempotentes | `get_or_create_collection` |
| `chromadb.Client()` es efímero por defecto | Los vectores pueden perderse al reiniciar | `PersistentClient` o vector DB gestionada |
| IDs `str(i)` se reinician en cada llamada a `ingest_documents` | Colisiones o errores al reingestar | IDs estables derivados de documento + versión + chunk |
| No hay control si la colección está vacía | Query puede fallar o producir resultados inesperados | Comprobar `count()` y abstenerse |
| Sin validación de pregunta vacía | Llamadas innecesarias y resultados ambiguos | Validar inputs |
| No hay manejo de excepciones, timeouts ni retries | Un error transitorio rompe la petición | Manejo centralizado de errores y política de retry en el cliente/infraestructura |
| Escritura de `history.json` sin `with` | Manejo de fichero deficiente | Context manager o, mejor, eliminar esta persistencia local |
| Mutación de `history` dentro de `ask` | Efecto lateral inesperado para el caller | Tratar historial como entrada inmutable y devolver estado explícito si fuese necesario |

### 2.3 Calidad RAG / diseño

| Problema | Impacto | Mejora |
|---|---|---|
| Se embebe cada documento completo | Documentos largos pueden superar límites y la recuperación pierde granularidad | Chunking con solape y metadatos |
| No existen página, versión, título ni ID de documento | No se pueden generar citas verificables | Metadata por chunk |
| No hay parsing de PDF/DOCX | Tablas e imágenes se perderían si se convierten mal a texto plano | Capa previa de extracción/layout; para tablas, preservar filas/cabeceras |
| `n_results=5` fijo sin umbral de relevancia | Siempre devuelve algo aunque sea irrelevante | Top-K configurable + threshold calibrado |
| Concatenación con espacios | Se pierde la frontera entre fuentes | Bloques delimitados y etiquetados `[S1]`, `[S2]`, etc. |
| No hay política de abstención | El LLM puede completar información que no está en los documentos | Si no hay evidencia suficiente, responder “no encuentro evidencia suficiente” |
| No hay control de versiones documentales | Puede recuperarse información obsoleta | Versionado y filtros de documentos activos |
| Historial completo entra siempre al prompt | Coste creciente, mayor latencia y riesgo de contaminación contextual | Ventana limitada o resumen controlado |
| No hay separación entre retrieval y generation | Difícil de testear y sustituir componentes | `VectorStore`, `RagService`, configuración y modelos separados |

### 2.4 Rendimiento y coste

| Problema | Impacto | Mejora |
|---|---|---|
| Una llamada de embeddings por documento | Latencia y overhead de red altos | Batch de embeddings |
| Reingesta completa sin deduplicación | Coste innecesario | IDs/hashes deterministas + upsert |
| Sin caché ni procesamiento incremental | Recalcula trabajo ya hecho | Reingesta solo de cambios |
| Sin presupuesto de contexto | Riesgo de prompts demasiado grandes | Limitar cantidad/tamaño de chunks y evaluar token budget |
| Modelo de generación fijado en código | Difícil equilibrar coste/calidad | Configurable por entorno |

### 2.5 Mantenibilidad y operabilidad

- Estado global creado al importar el módulo.
- Configuración mezclada con lógica de negocio.
- No hay tipos de dominio para documentos, chunks, citas o turnos.
- No hay tests.
- No hay logs estructurados ni métricas de latencia, retrieval hit/miss o tasa de abstención.
- No hay separación entre desarrollo, test y producción.
- Dependencia directa del SDK del proveedor en toda la lógica.
- No existe estrategia de migración de embedding model: cambiar el modelo invalida el índice existente y debe disparar reindexación.

---

## 3. Problemas específicos del SDK original

El código usa el estilo legado:

```python
openai.Embedding.create(...)
openai.ChatCompletion.create(...)
```

La versión mejorada usa un cliente explícito:

```python
from openai import OpenAI
client = OpenAI(api_key=...)
```

Además, el modelo de embeddings queda configurable y el ejemplo usa `text-embedding-3-small`. El modelo de generación también se configura por entorno para no atar el diseño a un identificador fijo.

---

## 4. Arquitectura propuesta

```text
              +---------------------------+
              |  PDF / DOCX parser previo |
              |  texto + page + version   |
              +-------------+-------------+
                            |
                            v
+------------------+   chunking + metadata   +-------------------+
| SourceDocument   | ----------------------> | Stable Chunk IDs  |
+------------------+                         +---------+---------+
                                                      |
                                          batch embeddings
                                                      |
                                                      v
                                            +---------+---------+
                                            | Chroma persistente |
                                            | (interfaz aislada) |
                                            +---------+---------+
                                                      |
User question --> embedding --> top-k + threshold --> evidence
                                                      |
                                                      v
                                            +---------+---------+
                                            | LLM generation    |
                                            | evidence != rules |
                                            +---------+---------+
                                                      |
                                             validate [S#]
                                                      |
                                                      v
                                             Answer + citations
```

### Por qué esta arquitectura

1. **Parsing separado de RAG**: evita fingir que `list[str]` representa fielmente un PDF complejo.
2. **Chunks con metadata**: una respuesta puede volver a la página/versión exacta.
3. **IDs estables + upsert**: la reingesta es idempotente.
4. **Vector store persistente**: reiniciar el proceso no borra el índice.
5. **Evidence boundary**: el texto recuperado se marca como datos, no como instrucciones.
6. **Abstención y validación de citas**: el backend no acepta una respuesta sin evidencia verificable.

---

## 5. Versión mejorada

La implementación completa está en `src/rag_review/`. El flujo principal queda deliberadamente pequeño:

```python
settings = Settings.from_env()
service = RagService(settings)

service.ingest_documents([
    SourceDocument(
        text="...",
        source="protocolo.pdf",
        page=12,
        version="3.2",
        document_id="protocol-renal",
    )
])

result = service.ask("¿Qué establece el protocolo?")
print(result.text)
print(result.citations)
```

### Decisiones implementadas

- Secretos por variables de entorno.
- Cliente moderno y único del proveedor.
- Chroma persistente.
- `get_or_create_collection`.
- Chunking determinista con solape.
- IDs SHA-256 estables.
- Metadata de fuente, página, versión y documento.
- Embeddings en batch.
- `upsert` en vez de `add` ciego.
- Top-K y threshold configurables.
- No llamar al LLM si no hay evidencia relevante.
- Historial acotado y no persistido a disco.
- Prompt con separación explícita entre instrucciones y evidencia.
- Citas `[S#]` generadas sobre un catálogo de fuentes conocido por backend.
- Rechazo de una respuesta si no contiene ninguna cita válida.

---

## 6. Qué no resuelve este snippet por sí solo

### PDF/Word, tablas e imágenes

La entrada original es `list[str]`; por tanto, no existe ninguna lógica que pueda garantizar que una tabla de dosificación haya sido extraída correctamente. En producción añadiría una etapa de parsing/layout que devuelva, como mínimo:

- `document_id`
- `source`
- `version`
- `page`
- `section`
- texto narrativo
- tablas preservando cabeceras + fila completa
- referencia a imagen/caption cuando aplique

### Datos de pacientes

Este repositorio debe considerarse **RAG documental**, no una integración con la base MySQL de pacientes. En el escenario clínico, preguntas con PHI no deberían enviarse automáticamente a un LLM externo. La frontera de datos sensibles debe implementarse fuera de este módulo, en un gateway local o capa equivalente.

### Persistencia de conversación

Se eliminó `history.json` deliberadamente. Si el producto necesita memoria de conversación, debe diseñarse con:

- sesiones/usuario,
- cifrado,
- retención,
- concurrencia,
- permisos,
- auditoría,
- y requisitos RGPD.

Un fichero JSON local no cumple esos objetivos.

---

## 7. Trade-offs de la solución

### Mantener Chroma en el ejercicio

Se conserva Chroma para que la mejora siga siendo comparable con el código recibido y el take-home sea fácil de ejecutar. Para una clínica desplegada en Azure con requisitos de operación más fuertes, consideraría PostgreSQL + pgvector porque reduce piezas y permite unir metadata estructurada, versionado y vectores en una única plataforma.

### Threshold de similitud

`MAX_DISTANCE=0.45` es solo un valor inicial, **no una verdad universal**. Debe calibrarse con un dataset de preguntas reales y medir precision/recall y tasa de abstención.

### Citas

Validar que `[S3]` existe impide referencias inventadas, pero no prueba automáticamente que la frase concreta esté correctamente respaldada por S3. Para producción añadiría evaluación de entailment/groundedness y tests “golden”.

---

## 8. Pruebas recomendadas

### Unitarias

- IDs estables para el mismo documento/version/chunk.
- No generar chunks para texto vacío.
- Rechazar `chunk_overlap >= chunk_size`.
- Pregunta vacía -> error controlado.
- Colección vacía -> abstención.
- Cita fuera del catálogo -> ignorada/rechazada.

### Integración

- Reingestar el mismo documento no duplica chunks.
- Cambiar versión genera nuevos IDs.
- Consulta irrelevante produce abstención.
- Reiniciar proceso mantiene el índice.
- El modelo nunca recibe API keys ni metadata secreta.

### Calidad RAG

Crear un dataset “golden” con:

- pregunta,
- documento esperado,
- página esperada,
- respuesta aceptable,
- casos sin respuesta,
- versiones antiguas vs activas.

Medir al menos retrieval recall@K, tasa de abstención correcta y groundedness de la respuesta.

---

## 9. Priorización

### P0 — antes de ejecutar en un entorno real

1. Rotar cualquier API key que haya sido expuesta.
2. Secretos fuera del código.
3. Persistencia real del índice.
4. Chunking + metadata + fuentes.
5. Abstención cuando no hay evidencia.
6. No persistir historial sensible en JSON.

### P1 — antes de producción

1. Parsing robusto de PDF/DOCX.
2. Versionado documental.
3. Observabilidad y alertas.
4. Retry/backoff/timeouts.
5. Tests de calidad RAG.
6. Política explícita para PHI/PII.

### P2 — evolución

1. Búsqueda híbrida lexical + vectorial.
2. Reranking.
3. Caché.
4. pgvector si se busca simplificar infraestructura productiva.
5. Evaluación automatizada continua.

---

## 10. Conclusión

El mayor problema del fragmento no es que “use Chroma” o que tenga pocas líneas. Es que mezcla secretos, estado, retrieval, prompting, historial y persistencia sin fronteras claras. La versión propuesta convierte esa PoC en una base testeable y mantenible, pero mantiene explícitos los límites: **el parser documental, la protección de datos de paciente y la gobernanza clínica son capas adicionales que no deben fingirse resueltas por el RAG**.
