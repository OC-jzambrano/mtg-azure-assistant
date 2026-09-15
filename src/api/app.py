import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from src.config import settings
from src.orchestrator import MTGOrchestrator
from src.api.schemas import ChatRequest, ChatResponse
from src.observability.tracing import tracing
from src.services.database import database

logger = logging.getLogger("mtg_assistant.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Optional Azure Monitor OpenTelemetry runtime configuration
    appinsights_cs = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if appinsights_cs:
        try:
            from azure.monitor.opentelemetry import configure_azure_monitor
            configure_azure_monitor(connection_string=appinsights_cs)
            logger.info("Azure Monitor OpenTelemetry configured successfully.")
        except Exception as exc:
            logger.warning("Could not initialize Azure Monitor OpenTelemetry: %s", exc)

    yield

    tracing.shutdown()
    database.close()


app = FastAPI(
    title="MTG Call Center AI Assistant API",
    description="API REST para asistente de soporte de Magic: The Gathering (RAG + MTG API)",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration
cors_origins_env = os.getenv("CORS_ORIGINS", "*")
allowed_origins = [o.strip() for o in cors_origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

orchestrator = MTGOrchestrator()
app.mount("/chat", StaticFiles(directory=Path(__file__).resolve().parents[1] / "ui" / "web", html=True), name="chat-ui")


@app.get("/")
def root():
    return {
        "service": "MTG Call Center Assistant",
        "docs": "/docs",
        "health": "/health",
        "ready": "/ready",
        "chat_ui": "/chat/"
    }


@app.get("/health")
def health():
    """Liveness probe: returns 200 immediately if process is alive."""
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.version
    }


@app.get("/ready")
def ready():
    """
    Readiness probe: validates database connectivity and vector readiness
    before Container Apps routes traffic to this revision.
    """
    db_reachable = database.is_reachable()
    vector_ready = database.is_vector_ready() if db_reachable else False

    is_ready = db_reachable
    http_status = status.HTTP_200_OK if is_ready else status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(
        status_code=http_status,
        content={
            "status": "ready" if is_ready else "not_ready",
            "database_reachable": db_reachable,
            "pgvector_ready": vector_ready,
            "rag_backend": settings.rag_backend,
            "service": settings.app_name,
            "version": settings.version
        }
    )


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    with tracing.chat_trace(
        conversation_id=req.conversation_id,
        message=req.message,
    ) as trace:
        result = orchestrator.handle_message(
            conversation_id=req.conversation_id,
            message=req.message,
            locale=req.locale
        )
        trace_output = tracing.build_root_output(result)
        trace.update(output=trace_output)

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
