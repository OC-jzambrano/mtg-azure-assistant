import os
from pathlib import Path
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseModel):
    app_name: str = "MTG Call Center Assistant"
    version: str = "1.0.0"
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    # External MTG API
    mtg_api_base_url: str = os.getenv("MTG_API_BASE_URL", "https://api.magicthegathering.io/v1")
    mtg_user_agent: str = "MTG-Assistant/1.0"
    
    # Azure OpenAI / OpenAI
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    azure_openai_endpoint: str = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    azure_openai_api_key: str = os.getenv("AZURE_OPENAI_API_KEY", "")
    azure_openai_deployment: str = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini")
    
    # Database
    database_url: str = os.getenv("DATABASE_URL", "")
    
    # Data paths
    rules_data_path: Path = BASE_DIR / "data" / "official_rules_mtg.json"

settings = Settings()
