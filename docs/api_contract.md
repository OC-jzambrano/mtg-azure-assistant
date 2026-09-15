# Contrato Oficial de la API: `/api/chat`

Este documento define la frontera contractual estable e inmutable entre el frontend (**chat web NLUX**) y el backend (**FastAPI**), así como para cualquier cliente externo o canal de Call Center.

---

## 1. Especificación del Endpoint

* **Método**: `POST`
* **Ruta**: `/api/chat`
* **Content-Type**: `application/json`

---

## 2. Esquema de Petición (Request)

```json
{
  "conversation_id": "string (UUIDv4 o identificador estable de sesión)",
  "message": "string (1 - 4000 caracteres)"
}
```

### Campos:
| Campo | Tipo | Requerido | Descripción |
| :--- | :--- | :--- | :--- |
| `conversation_id` | `string` | Sí | Identificador único de la conversación generado por el cliente (ej. UUID). Se mantiene en todos los turnos. |
| `message` | `string` | Sí | Mensaje del usuario en lenguaje natural. |

---

## 3. Esquema de Respuesta (Response)

```json
{
  "conversation_id": "string",
  "type": "rules | card_search | custom_card | conversation",
  "message": "string",
  "cards": [
    {
      "name": "string",
      "mana_cost": "string | null",
      "cmc": "number | null",
      "type_line": "string | null",
      "oracle_text": "string | null",
      "image_url": "string | null",
      "set_name": "string | null"
    }
  ],
  "sources": [
    {
      "kind": "rule | external_api | design",
      "title": "string",
      "reference": "string | null",
      "url": "string | null"
    }
  ],
  "active_filters": {
    "color": "string | null",
    "subtype": "string | null",
    "card_type": "string | null",
    "cmc": "integer | null",
    "max_cmc": "integer | null"
  } | null
}
```

---

## 4. Ejemplos por Tipo de Respuesta

### A. Flujo de Reglas (`type: "rules"`)
**Petición:**
```json
{
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "¿Cómo funciona el maná?"
}
```

**Respuesta:**
```json
{
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
  "type": "rules",
  "message": "**Funcionamiento del Maná en Magic: The Gathering (CR 106.1)**...",
  "cards": [],
  "sources": [
    {
      "kind": "rule",
      "title": "Magic Comprehensive Rules",
      "reference": "CR 106.1",
      "url": null
    },
    {
      "kind": "rule",
      "title": "Magic Comprehensive Rules",
      "reference": "CR 106.2",
      "url": null
    }
  ],
  "active_filters": null
}
```

---

### B. Flujo de Búsqueda de Cartas (`type: "card_search"`)
**Petición:**
```json
{
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Busco una carta blanca guerrero de coste inferior a 2"
}
```

**Respuesta:**
```json
{
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
  "type": "card_search",
  "message": "He encontrado 4 cartas que cumplen tus criterios (color W, subtipo Warrior, coste <= 1).",
  "cards": [
    {
      "name": "Dragon Hunter",
      "mana_cost": "{W}",
      "cmc": 1.0,
      "type_line": "Creature — Human Warrior",
      "oracle_text": "Protection from Dragons",
      "image_url": "http://gatherer.wizards.com/Handlers/Image.ashx?multiverseid=394541&type=card",
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

---

### C. Flujo Multi-turno (Acumulación Contextual de Filtros)

**Turno 1:**
```json
{
  "conversation_id": "session-multi-123",
  "message": "Busca una carta blanca guerrero"
}
```
*Respuesta activa:* `active_filters: {"color": "W", "subtype": "Warrior", "cmc": null, "max_cmc": null}`

**Turno 2 (Repregunta elíptica):**
```json
{
  "conversation_id": "session-multi-123",
  "message": "¿Y alguna que cueste solo uno?"
}
```
*Respuesta acumulada:*
```json
{
  "conversation_id": "session-multi-123",
  "type": "card_search",
  "message": "He encontrado cartas que cumplen tus criterios (color W, subtipo Warrior, coste exacto 1).",
  "cards": [...],
  "sources": [...],
  "active_filters": {
    "color": "W",
    "subtype": "Warrior",
    "card_type": null,
    "cmc": 1,
    "max_cmc": null
  }
}
```

---

### D. Flujo de Carta Custom (`type: "custom_card"`)
**Petición:**
```json
{
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Quiero una carta de Han Solo, blanca-roja con dañar primero"
}
```

**Respuesta:**
```json
{
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
  "type": "custom_card",
  "message": "### 🃏 Carta Custom Creada: Han Solo, Capitán del Halcón...",
  "cards": [
    {
      "name": "Han Solo, Capitán del Halcón",
      "mana_cost": "{1}{R}{W}",
      "cmc": 3.0,
      "type_line": "Legendary Creature — Human Rogue Pilot",
      "oracle_text": "Dañar primero. Disparó primero: Siempre que Han Solo ataque o bloquee...",
      "image_url": null,
      "set_name": null
    }
  ],
  "sources": [],
  "active_filters": null
}
```

---

### E. Flujo de Conversación General (`type: "conversation"`)
**Petición:**
```json
{
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Hola buenas tardes"
}
```

**Respuesta:**
```json
{
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
  "type": "conversation",
  "message": "¡Hola! Soy tu asistente y juez de soporte para Magic: The Gathering del Call Center...",
  "cards": [],
  "sources": [],
  "active_filters": null
}
```

---

## 5. Manejo de Errores

* **400 Bad Request**: Mensaje vacío o compuesto únicamente de espacios en blanco (`{"detail": "Message cannot be empty"}`).
* **422 Unprocessable Entity**: Cuerpos JSON mal formados que violan la validación Pydantic (ej. campos faltantes o tipos incorrectos).
* **500 Internal Server Error**: Excepciones no controladas en el servidor.
