from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from src.orchestrator import MTGOrchestrator
from src.config import settings

app = FastAPI(
    title="MTG Call Center AI Assistant",
    description="Asistente de soporte para Call Center de Magic: The Gathering con RAG y búsqueda en API oficial",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

orchestrator = MTGOrchestrator()

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default-session"

class ChatResponse(BaseModel):
    reply: str
    intent: str
    sources: List[str] = []
    cards: List[Dict[str, Any]] = []
    active_filters: Optional[Dict[str, Any]] = None

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.version
    }

@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    
    result = orchestrator.handle_message(
        session_id=req.session_id or "default-session",
        message=req.message
    )
    return ChatResponse(**result)

@app.get("/api/history/{session_id}")
def get_history(session_id: str):
    history = orchestrator.memory.get_recent_history(session_id)
    return {"session_id": session_id, "messages": [m.model_dump() for m in history]}

@app.get("/", response_class=HTMLResponse)
def index_ui():
    return """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>MTG Call Center AI Assistant</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
        <style>
            :root {
                --bg: #0f172a;
                --panel: #1e293b;
                --accent: #3b82f6;
                --accent-hover: #2563eb;
                --text: #f8fafc;
                --text-dim: #94a3b8;
                --border: #334155;
            }
            * { box-sizing: border-box; margin: 0; padding: 0; }
            body {
                font-family: 'Inter', sans-serif;
                background: var(--bg);
                color: var(--text);
                height: 100vh;
                display: flex;
                flex-direction: column;
            }
            header {
                padding: 1rem 2rem;
                background: var(--panel);
                border-bottom: 1px solid var(--border);
                display: flex;
                align-items: center;
                justify-content: space-between;
            }
            .brand { display: flex; align-items: center; gap: 0.75rem; }
            .brand h1 { font-size: 1.25rem; font-weight: 700; color: #60a5fa; }
            .badge {
                background: #1e3a8a;
                color: #93c5fd;
                padding: 0.25rem 0.6rem;
                border-radius: 9999px;
                font-size: 0.75rem;
                font-weight: 600;
            }
            .chat-container {
                flex: 1;
                overflow-y: auto;
                padding: 1.5rem;
                display: flex;
                flex-direction: column;
                gap: 1rem;
                max-width: 960px;
                margin: 0 auto;
                width: 100%;
            }
            .msg {
                display: flex;
                flex-direction: column;
                max-width: 85%;
                padding: 1rem;
                border-radius: 1rem;
                line-height: 1.5;
                font-size: 0.95rem;
            }
            .msg.user {
                align-self: flex-end;
                background: var(--accent);
                color: white;
                border-bottom-right-radius: 0.25rem;
            }
            .msg.assistant {
                align-self: flex-start;
                background: var(--panel);
                border: 1px solid var(--border);
                border-bottom-left-radius: 0.25rem;
            }
            .sources {
                margin-top: 0.75rem;
                padding-top: 0.75rem;
                border-top: 1px dashed var(--border);
                font-size: 0.8rem;
                color: var(--text-dim);
            }
            .cards-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
                gap: 0.75rem;
                margin-top: 0.75rem;
            }
            .card-box {
                background: #0b1329;
                border: 1px solid var(--border);
                border-radius: 0.5rem;
                overflow: hidden;
                text-align: center;
                padding: 0.5rem;
            }
            .card-box img {
                width: 100%;
                border-radius: 0.35rem;
                object-fit: cover;
                background: #111;
            }
            .card-title {
                font-size: 0.8rem;
                font-weight: 600;
                margin-top: 0.4rem;
                color: #e2e8f0;
            }
            .quick-prompts {
                display: flex;
                flex-wrap: wrap;
                gap: 0.5rem;
                padding: 0.75rem 1.5rem;
                max-width: 960px;
                margin: 0 auto;
                width: 100%;
            }
            .chip {
                background: var(--panel);
                border: 1px solid var(--border);
                color: var(--text-dim);
                padding: 0.4rem 0.8rem;
                border-radius: 9999px;
                font-size: 0.8rem;
                cursor: pointer;
                transition: all 0.2s;
            }
            .chip:hover {
                border-color: var(--accent);
                color: var(--text);
            }
            .input-area {
                padding: 1rem 1.5rem;
                background: var(--panel);
                border-top: 1px solid var(--border);
            }
            .input-box {
                max-width: 960px;
                margin: 0 auto;
                display: flex;
                gap: 0.75rem;
            }
            input[type="text"] {
                flex: 1;
                padding: 0.8rem 1.2rem;
                border-radius: 0.75rem;
                border: 1px solid var(--border);
                background: var(--bg);
                color: var(--text);
                font-size: 0.95rem;
                outline: none;
            }
            input[type="text"]:focus { border-color: var(--accent); }
            button {
                padding: 0.8rem 1.5rem;
                border-radius: 0.75rem;
                border: none;
                background: var(--accent);
                color: white;
                font-weight: 600;
                cursor: pointer;
                transition: background 0.2s;
            }
            button:hover { background: var(--accent-hover); }
        </style>
    </head>
    <body>
        <header>
            <div class="brand">
                <span style="font-size: 1.5rem;">🪄</span>
                <div>
                    <h1>MTG Judge & Call Center AI</h1>
                    <div style="font-size: 0.75rem; color: var(--text-dim);">FastAPI • RAG pgvector • MTG API • Azure Ready</div>
                </div>
            </div>
            <span class="badge">Online Demo</span>
        </header>

        <div class="quick-prompts">
            <span class="chip" onclick="sendPrompt('¿Cómo funciona el maná?')">💧 ¿Cómo funciona el maná?</span>
            <span class="chip" onclick="sendPrompt('¿Qué fases hay en un turno?')">⏳ Fases del turno</span>
            <span class="chip" onclick="sendPrompt('Mi rapaz del campo de batalla hizo daño primero y uso Ninja de horas tardías ¿aplico el daño?')">⚔️ Rapaz + Ninja Ninjutsu</span>
            <span class="chip" onclick="sendPrompt('Busco una carta de color blanco de coste inferior a dos que sea guerrero')">🔍 Blanca guerrero coste < 2</span>
            <span class="chip" onclick="sendPrompt('¿Y alguna que cueste solo uno?')">🔄 ¿Y alguna que cueste solo 1?</span>
            <span class="chip" onclick="sendPrompt('Quiero una carta de Han Solo, blanca-roja con dañar primero')">⭐ Carta Han Solo Custom</span>
        </div>

        <div class="chat-container" id="chat">
            <div class="msg assistant">
                <strong>¡Hola! Soy tu asistente de soporte para Magic: The Gathering.</strong><br>
                Puedo responder consultas sobre reglas oficiales (RAG), resolver interacciones complejas de combate, buscar cartas con imágenes en la API oficial y diseñar cartas custom.
            </div>
        </div>

        <div class="input-area">
            <div class="input-box">
                <input type="text" id="userInput" placeholder="Escribe tu consulta sobre reglas o búsqueda de cartas..." onkeypress="handleKey(event)">
                <button onclick="send()">Enviar</button>
            </div>
        </div>

        <script>
            const sessionId = "session-" + Math.random().toString(36).substring(7);

            function handleKey(e) {
                if (e.key === 'Enter') send();
            }

            function sendPrompt(text) {
                document.getElementById('userInput').value = text;
                send();
            }

            async function send() {
                const input = document.getElementById('userInput');
                const text = input.value.trim();
                if (!text) return;

                input.value = '';
                appendMessage('user', text);

                try {
                    const res = await fetch('/api/chat', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ message: text, session_id: sessionId })
                    });
                    const data = await res.json();
                    appendMessage('assistant', data.reply, data.sources, data.cards);
                } catch (err) {
                    appendMessage('assistant', 'Error de conexión con el servidor backend.');
                }
            }

            function appendMessage(role, text, sources = [], cards = []) {
                const chat = document.getElementById('chat');
                const msg = document.createElement('div');
                msg.className = 'msg ' + role;

                let html = '<div>' + text.replace(/\\n/g, '<br>') + '</div>';

                if (cards && cards.length > 0) {
                    html += '<div class="cards-grid">';
                    for (const c of cards) {
                        if (c.image_url) {
                            html += <div class="card-box">
                                <img src="" alt="" onerror="this.style.display='none'">
                                <div class="card-title"> ()</div>
                            </div>;
                        }
                    }
                    html += '</div>';
                }

                if (sources && sources.length > 0) {
                    html += '<div class="sources"><strong>Fuentes / Citaciones:</strong><br>';
                    sources.forEach(s => { html += • <br>; });
                    html += '</div>';
                }

                msg.innerHTML = html;
                chat.appendChild(msg);
                chat.scrollTop = chat.scrollHeight;
            }
        </script>
    </body>
    </html>
    """
