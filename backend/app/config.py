from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent

# ==========================================================
# Project Directories
# ==========================================================

DOCS_DIR = PROJECT_DIR / "docs"
UPLOADS_DIR = DOCS_DIR / "uploads"
CACHE_DIR = DOCS_DIR / "cache"

DATA_DIR = PROJECT_DIR / "data"

SCRIPTS_DIR = PROJECT_DIR / "scripts"
DOCKER_DIR = PROJECT_DIR / "docker"


class Settings(BaseSettings):
    # ==========================================================
    # Application
    # ==========================================================
    app_name: str = "IT Copilot"
    app_version: str = "0.2.0"
    app_description: str = "AI-powered IT assistant for employee self-service troubleshooting, ticketing, and audit."

    # ==========================================================
    # Environment
    # ==========================================================
    environment: str = "development"
    debug: bool = True
    log_level: str = "INFO"

    # ==========================================================
    # Storage
    # ==========================================================
    knowledge_base_directory: Path = DOCS_DIR
    uploads_directory: Path = UPLOADS_DIR
    cache_directory: Path = CACHE_DIR
    data_directory: Path = DATA_DIR
    vector_store_directory: Path = DATA_DIR / "vector_store"
    database_path: Path = DATA_DIR / "it_copilot.db"
    audit_log_path: Path = DATA_DIR / "audit_log.jsonl"

    # ==========================================================
    # Assistant
    # ==========================================================
    escalation_confidence_threshold: float = 0.6
    max_clarifying_questions: int = 3
    auto_ticket_on_resolution: bool = True

    # ==========================================================
    # AI
    # ==========================================================
    # NOTE: never hardcode API keys here. Put IT_COPILOT_ANTHROPIC_API_KEY
    # in a .env file (see .env.example). The .env file is gitignored.
    anthropic_api_key: str = ""
    chat_model: str = "claude-sonnet-5"
    embedding_model: str = "local"

    model_config = SettingsConfigDict(
        env_file=PROJECT_DIR / ".env",
        env_file_encoding="utf-8",
        env_prefix="IT_COPILOT_",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
