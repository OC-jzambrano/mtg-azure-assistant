import os
from pathlib import Path
from pydantic import BaseModel
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

class Settings(BaseModel):
    app_name: str = "MTG Call Center Assistant"
    version: str = "1.0.0"
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"
    app_environment: str = os.getenv("APP_ENV", "local")
    
    # External MTG API
    mtg_api_base_url: str = os.getenv("MTG_API_BASE_URL", "https://api.magicthegathering.io/v1")
    mtg_user_agent: str = "MTG-Assistant/1.0"
    
    # Azure OpenAI / OpenAI
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    azure_openai_endpoint: str = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    azure_openai_api_key: str = os.getenv("AZURE_OPENAI_API_KEY", "")
    azure_openai_deployment: str = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini")
    azure_openai_deployment_reasoning: str = os.getenv("AZURE_OPENAI_DEPLOYMENT_REASONING", "gpt-4o")
    
    # Langfuse AI Observability
    langfuse_enabled: bool = os.getenv("LANGFUSE_ENABLED", "false").lower() == "true"
    langfuse_public_key: str = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    langfuse_secret_key: str = os.getenv("LANGFUSE_SECRET_KEY", "")
    langfuse_base_url: str = os.getenv("LANGFUSE_BASE_URL", "https://cloud.langfuse.com")
    langfuse_capture_content: bool = os.getenv("LANGFUSE_CAPTURE_CONTENT", "true").lower() == "true"
    
    # Database
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql://mtg_admin:mtg_secure_password_123@localhost:5432/mtg_callcenter_db"
    )
    
    # Embeddings
    azure_openai_embedding_deployment: str = os.getenv(
        "AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small"
    )
    embedding_dimensions: int = int(os.getenv("EMBEDDING_DIMENSIONS", "1536"))
    
    # RAG Configuration
    rag_backend: str = os.getenv("RAG_BACKEND", "auto")  # 'auto', 'pgvector', 'lexical'
    rag_top_k: int = int(os.getenv("RAG_TOP_K", "3"))

    # Data paths
    rules_data_path: Path = BASE_DIR / "data" / "official_rules_mtg.json"

settings = Settings()
