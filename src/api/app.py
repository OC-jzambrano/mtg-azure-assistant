from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src.config import settings
from src.orchestrator import MTGOrchestrator
from src.api.schemas import ChatRequest, ChatResponse

app = FastAPI(
    title="MTG Call Center AI Assistant API",
    description="API REST para asistente de soporte de Magic: The Gathering (RAG + MTG API)",
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


@app.get("/")
def root():
    return {
        "service": "MTG Call Center Assistant",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.version
    }


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    result = orchestrator.handle_message(
        conversation_id=req.conversation_id,
        message=req.message
    )

    return ChatResponse(
        conversation_id=req.conversation_id,
        type=result.type,
        message=result.message,
        cards=result.cards,
        sources=result.sources,
        active_filters=result.active_filters
    )


@app.get("/api/history/{conversation_id}")
def get_history(conversation_id: str):
    history = orchestrator.memory.get_recent_history(conversation_id)
    return {
        "conversation_id": conversation_id,
        "messages": [m.model_dump() for m in history]
    }
