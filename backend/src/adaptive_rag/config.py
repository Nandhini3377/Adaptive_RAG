"""App settings, loaded from environment variables and the .env file."""

import secrets
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# config.py lives in backend/src/adaptive_rag/, so the project root is 3 folders up
PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """All tunable values in one place."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM
    sarvam_api_key: SecretStr = SecretStr("")
    sarvam_base_url: str = "https://api.sarvam.ai/v1"
    sarvam_model: str = "sarvam-105b"
    llm_timeout_seconds: float = 120.0
    llm_max_retries: int = 3
    # Extra tries when a reasoning model thinks past max_tokens without answering
    llm_truncation_retries: int = 1
    # Price in INR per million tokens (PRD Section 14); reasoning counts as output
    llm_input_price_inr: float = 29.28
    llm_output_price_inr: float = 73.20
    # Reuse saved answers for identical calls (dev and eval cost ~nothing)
    llm_cache_enabled: bool = True
    # Sarvam reasons for ~1-4K tokens before answering (measured), rarely more
    answer_max_tokens: int = 8000

    # Auth
    # Set JWT_SECRET in .env so logins survive restarts; if empty, a random
    # secret is made at startup (safe, but everyone is logged out on restart)
    jwt_secret: SecretStr = SecretStr("")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24

    # API
    cors_origins: list[str] = ["http://localhost:3000"]

    # Uploads
    max_upload_mb: int = 50

    # Local models
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    # BGE models search better when questions (not chunks) carry this instruction
    embedding_query_prefix: str = "Represent this sentence for searching relevant passages: "
    reranker_model: str = "BAAI/bge-reranker-base"

    # Storage
    data_dir: Path = PROJECT_ROOT / "data"
    # Empty means SQLite at data/app.db; set a URL to use another database
    database_url: str = ""

    @property
    def db_url(self) -> str:
        """The database URL actually used."""
        return self.database_url or f"sqlite:///{self.data_dir / 'app.db'}"

    @property
    def upload_dir(self) -> Path:
        """Where original uploaded files are kept."""
        return self.data_dir / "uploads"

    # Chunking: ~1500 characters is ~300-400 tokens, inside the embedder's 512 limit
    chunk_max_chars: int = 1500

    # Retrieval
    top_k: int = 5


settings = Settings()
if not settings.jwt_secret.get_secret_value():
    settings.jwt_secret = SecretStr(secrets.token_urlsafe(32))
