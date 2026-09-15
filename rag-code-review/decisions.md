# Documento de Decisiones Técnicas (DDT)

## DDT-001 — Secretos fuera del código

**Estado:** Aceptada  
**Contexto:** El código original contiene la API key en una constante.  
**Decisión:** Leer secretos desde entorno/secret manager y excluir `.env` de Git.  
**Alternativas:** Config file versionado; key hardcodeada.  
**Consecuencias:** Requiere configurar el entorno, pero permite rotación y evita filtraciones triviales.

---

## DDT-002 — Mantener Chroma para el take-home, detrás de una interfaz

**Estado:** Aceptada para el ejercicio; revisar en producción.  
**Contexto:** El código original ya usa Chroma y el entregable debe ser fácil de ejecutar.  
**Decisión:** Usar `PersistentClient` y encapsular acceso en `ChromaVectorStore`.  
**Alternativas:** PostgreSQL + pgvector, Qdrant, Pinecone, Azure AI Search.  
**Consecuencias:** Menor cambio y menor fricción local. En una clínica Azure, pgvector puede ser preferible para reducir componentes y combinar metadata/vectores.

---

## DDT-003 — Parsing documental fuera del servicio RAG

**Estado:** Aceptada.  
**Contexto:** La función original recibe `list[str]`; no recibe PDFs ni Word.  
**Decisión:** El RAG trabaja con `SourceDocument(text, source, page, version, ...)`. Un pipeline anterior es responsable de extracción/layout.  
**Alternativas:** Hacer que `RagService` abra PDF/DOCX directamente.  
**Consecuencias:** Mejor separación de responsabilidades y posibilidad de sustituir el parser sin tocar retrieval/generation.

---

## DDT-004 — Chunking con metadata e IDs deterministas

**Estado:** Aceptada.  
**Contexto:** Embedir documentos completos degrada recuperación y no permite citas precisas. IDs incrementales colisionan al reingestar.  
**Decisión:** Dividir en chunks solapados y generar ID SHA-256 con identidad de documento, versión, página, índice y contenido.  
**Alternativas:** UUID aleatorio por chunk; índice incremental.  
**Consecuencias:** Upserts idempotentes, deduplicación y trazabilidad. Cambiar el algoritmo de chunking puede requerir reindexación.

---

## DDT-005 — Embeddings por lotes

**Estado:** Aceptada.  
**Contexto:** El original hace una petición por documento.  
**Decisión:** Enviar batches configurables al endpoint de embeddings.  
**Alternativas:** Una llamada por chunk.  
**Consecuencias:** Menor latencia/overhead; se debe respetar el límite de entrada del proveedor.

---

## DDT-006 — Umbral de relevancia + abstención

**Estado:** Aceptada.  
**Contexto:** `n_results=5` siempre entrega cinco vecinos aunque sean irrelevantes.  
**Decisión:** Filtrar por distancia y no invocar al LLM cuando no hay evidencia suficiente.  
**Alternativas:** Siempre generar una respuesta.  
**Consecuencias:** Menos alucinación; aumenta la tasa de “no sé”. El threshold debe calibrarse con datos reales.

---

## DDT-007 — Evidencia no es instrucción

**Estado:** Aceptada.  
**Contexto:** El original concatena el documento recuperado al mensaje `system`.  
**Decisión:** Mantener las instrucciones del sistema separadas y delimitar la evidencia como datos no confiables.  
**Alternativas:** Meter todo en `system`.  
**Consecuencias:** Reduce superficie de prompt injection, aunque no elimina todos los ataques; requiere defensa en profundidad.

---

## DDT-008 — Citas controladas por backend

**Estado:** Aceptada.  
**Contexto:** El requerimiento de negocio necesita fuentes concretas.  
**Decisión:** Etiquetar chunks recuperados como `[S1]...[Sn]`, exigir esas referencias y validar que existan antes de aceptar la respuesta.  
**Alternativas:** Pedir al LLM que escriba título/página libremente.  
**Consecuencias:** Evita referencias inexistentes y desacopla presentación de metadata. No sustituye una evaluación semántica de soporte factual.

---

## DDT-009 — No persistir historial en JSON local

**Estado:** Aceptada.  
**Contexto:** El original sobrescribe `history.json` en cada consulta.  
**Decisión:** El servicio recibe historial como input, lo limita a N turnos y no lo persiste.  
**Alternativas:** JSON local; SQLite; base de datos de sesiones.  
**Consecuencias:** Ejemplo seguro por defecto. Si se necesita memoria persistente, será un componente explícito con cifrado, usuarios, retención y concurrencia.

---

## DDT-010 — RAG documental separado de PHI

**Estado:** Aceptada para el escenario clínico.  
**Contexto:** La clínica tiene datos sensibles en MySQL que no deben salir del sistema.  
**Decisión:** Este módulo no consulta MySQL ni recibe ECG. La capa que detecta/gestiona PHI vive antes del RAG cloud.  
**Alternativas:** Dar al LLM acceso a MySQL mediante SQL/tool/MCP.  
**Consecuencias:** Menor superficie de exposición y privilegio. Los cálculos con variables clínicas requieren un servicio local separado.

---

## DDT-011 — Modelo configurable

**Estado:** Aceptada.  
**Contexto:** El original fija `gpt-4` y `text-embedding-ada-002`.  
**Decisión:** Modelo de generación y embeddings se seleccionan por variables de entorno.  
**Alternativas:** IDs hardcodeados.  
**Consecuencias:** Facilita coste/entorno/migraciones. Cambiar el embedding model obliga a reindexar o versionar el índice.

---
