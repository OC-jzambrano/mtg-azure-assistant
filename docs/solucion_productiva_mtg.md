# Guía de la Solución: MTG Call Center Assistant
**Asistente Inteligente y Juez de Reglas para Magic: The Gathering en Microsoft Azure**

---

## 1. ¿Qué es este sistema?

El **MTG Call Center Assistant** es una aplicación diseñada para ayudar tanto a operadores de soporte técnico como a jugadores a resolver cualquier consulta sobre el juego de cartas *Magic: The Gathering*.

El objetivo principal es responder con **precisión técnica oficial, rapidez y cero inventos (alucinaciones)**:
- Si se pregunta por una regla oficial, cita el artículo exacto del reglamento (*Comprehensive Rules*).
- Si se busca una carta, consulta la base de datos oficial en tiempo real.
- Si se pide diseñar una carta nueva, la crea de forma equilibrada respetando las reglas de diseño del juego.

---

## 2. ¿Qué puede hacer? (Los 4 Casos de Uso)

El asistente está preparado para resolver cuatro tipos de situaciones habituales:

### 1. Consultas de Reglas y Combate
- **Ejemplo**: *"¿Qué ocurre si ataco con una criatura que tiene Dañar primero y activo Ninjutsu?"*
- **Cómo responde**: Actúa como un **Juez Oficial (Nivel 3)**. Analiza paso a paso la situación de juego, el orden de las fases y cita las reglas oficiales aplicables (por ejemplo, `CR 702.48c` y `CR 702.7b`).

### 2. Búsqueda de Cartas en Lenguaje Natural
- **Ejemplo**: *"Busco una criatura blanca guerrero que cueste menos de dos manás"*.
- **Cómo responde**: Traduce la frase del usuario a filtros precisos (`color: Blanco`, `subtipo: Guerrero`, `coste <= 1`) y muestra las cartas reales encontradas con su imagen oficial y enlace a Gatherer.

### 3. Conversación Continua (Memoria Contextual)
- **Ejemplo**: Tras la búsqueda anterior, el usuario añade: *"¿Y alguna que cueste solo uno?"*.
- **Cómo responde**: El asistente recuerda que estábamos buscando guerreros blancos y solo modifica el filtro de coste, sin obligar al usuario a repetir toda la información.

### 4. Creación de Cartas Personalizadas
- **Ejemplo**: *"Créame una carta ficticia de Han Solo, blanca y roja con Dañar primero"*.
- **Cómo responde**: Diseña una carta balanceada según la filosofía del *Color Pie* (combinación de colores, coste justo y habilidades coherentes), indicando de forma transparente que no tiene imagen en lugar de inventar enlaces rotos.

---

## 3. ¿Qué servicios en la nube utiliza? (Microsoft Azure)

Para que la solución sea fiable y económica en producción, utiliza servicios gestionados en **Microsoft Azure** (región `swedencentral`):

1. **Azure Container Apps**:
   - Es el hogar de la aplicación. Aloja tanto la interfaz web de chat como la API (FastAPI).
   - Escala de forma automática: si hay muchas consultas añade réplicas, y si baja el tráfico se reduce para ahorrar costes.

2. **Azure Database for PostgreSQL 16 (con extensión `VECTOR`)**:
   - Es el cerebro de datos unificado.
   - Guarda las reglas oficiales en vectores para poder buscarlas por significado (*pgvector*), almacena el historial de las conversaciones y guarda en caché las cartas consultadas para no repetir llamadas lentas a internet.
   - **Sin complicaciones añadidas**: al usar PostgreSQL para todo, no se necesitan bases de datos extra como Redis.

3. **Azure OpenAI Service**:
   - Aporta los modelos de lenguaje:
     - `gpt-4o`: Se encarga del razonamiento complejo de reglas y del diseño creativo de cartas.
     - `text-embedding-3-small`: Convierte las preguntas en vectores para encontrar la regla adecuada en milisegundos.

4. **Azure Key Vault**:
   - La caja fuerte de la aplicación. Guarda de forma segura las contraseñas y claves de API para que nunca estén escritas en el código.

---

## 4. ¿Cómo colaboran los Agentes de Inteligencia Artificial?

En lugar de crear un enjambre confuso de muchos bots, el sistema utiliza un modelo claro de **especialistas**:

- **El Enrutador (Router Central)**:
  - Es el primer punto de contacto. Analiza el mensaje del usuario en **menos de 10 milisegundos** sin gastar dinero en inteligencia artificial.
  - Detecta si la pregunta es de reglas, de búsqueda o de diseño de cartas, y la envía directamente al especialista correspondiente.

- **El Juez de Reglas (Rules Reasoning Agent)**:
  - Es el agente cognitivo más potente. Sigue un método de razonamiento en 4 pasos obligatorios:
    1. Revisa qué cartas están en la mesa y qué habilidades tienen.
    2. Comprueba en qué fase del turno ocurre la acción.
    3. Consulta los artículos oficiales del reglamento (*Comprehensive Rules*).
    4. Emite un veredicto claro y directo para el jugador.
  - *Resiliencia*: Si la conexión con Azure OpenAI fallara en algún momento, el sistema tiene un modo local que responde a las preguntas principales sin interrumpir el servicio.

- **El Diseñador de Cartas (Custom Card Agent)**:
  - Genera cartas personalizadas que respetan las normas del juego, asegurando que la fuerza, resistencia y coste sean justos.

- **El Buscador de Cartas (Herramienta directa)**:
  - Realiza las búsquedas directamente en la API oficial de Magic sin necesidad de inventar nada.

---

## 5. Monitorización: ¿Cómo sabemos que el sistema funciona bien?

La solución vigila la salud del sistema en dos niveles independientes:

### Observabilidad de la Inteligencia Artificial (Langfuse Cloud)
- Registra cada conversación para que los administradores puedan ver qué respondió el asistente.
- Mide el tiempo exacto que tarda cada modelo en contestar.
- Cuenta los tokens utilizados y el coste económico en tiempo real.
- **Privacidad**: Filtra automáticamente cualquier contraseña, clave de API o dato confidencial antes de guardarlo.

### Monitorización del Servidor (Azure Application Insights)
- Comprueba que la aplicación web esté respondiendo de manera fluida.
- Detecta si hay errores en el servidor o lentitud en las consultas a la base de datos.
- Cuenta con dos comprobaciones automáticas de salud:
  - `/health`: Confirma que la aplicación está viva.
  - `/ready`: Confirma que la base de datos PostgreSQL está conectada y lista para atender usuarios.

---

## 6. Enlaces Útiles

- 🌐 **Chat en Vivo en Azure**: [https://mtg-assistant-app.ashyisland-b6708f09.swedencentral.azurecontainerapps.io/chat/](https://mtg-assistant-app.ashyisland-b6708f09.swedencentral.azurecontainerapps.io/chat/)
- 📑 **Documentación Swagger de la API**: [https://mtg-assistant-app.ashyisland-b6708f09.swedencentral.azurecontainerapps.io/docs](https://mtg-assistant-app.ashyisland-b6708f09.swedencentral.azurecontainerapps.io/docs)
- 🏛️ **Diagrama Interactivo de Arquitectura**: [`docs/architecture.html`](docs/architecture.html)
- 🔭 **Panel de Trazas y Métricas de IA**: [https://cloud.langfuse.com](https://cloud.langfuse.com)
