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
    app_name: str = "TriageBot"
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
    database_path: Path = DATA_DIR / "triagebot.db"
    audit_log_path: Path = DATA_DIR / "audit_log.jsonl"

    # ==========================================================
    # Assistant
    # ==========================================================
    escalation_confidence_threshold: float = 0.6
    max_clarifying_questions: int = 3
    auto_ticket_on_resolution: bool = True

    # ==========================================================
    # Security escalation
    # ==========================================================
    # Named humans (Slack user IDs, emails) paged directly for
    # security incidents. A channel post alone is not an escalation.
    security_responders: str = ""

    # A security incident must be acknowledged by a responder within
    # this window, or the watchdog re-escalates it, loudly.
    security_ack_deadline_minutes: int = 15

    # ==========================================================
    # AI
    # ==========================================================
    # NOTE: never hardcode API keys here. Put TRIAGEBOT_ANTHROPIC_API_KEY
    # in a .env file (see .env.example). The .env file is gitignored.
    anthropic_api_key: str = ""
    chat_model: str = "claude-sonnet-5"
    embedding_model: str = "local"

    model_config = SettingsConfigDict(
        env_file=PROJECT_DIR / ".env",
        env_file_encoding="utf-8",
        env_prefix="TRIAGEBOT_",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def security_responder_list(self) -> list[str]:
        """Comma-separated responder handles, as a clean list."""
        return [
            handle.strip()
            for handle in self.security_responders.split(",")
            if handle.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
