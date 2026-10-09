"""App settings, loaded from environment variables and the .env file."""

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
    # Price in INR per million tokens (PRD Section 14); reasoning counts as output
    llm_input_price_inr: float = 29.28
    llm_output_price_inr: float = 73.20

    # Local models
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    # BGE models search better when questions (not chunks) carry this instruction
    embedding_query_prefix: str = (
        "Represent this sentence for searching relevant passages: "
    )
    reranker_model: str = "BAAI/bge-reranker-base"

    # Storage
    data_dir: Path = PROJECT_ROOT / "data"

    # Chunking: ~1500 characters is ~300-400 tokens, inside the embedder's 512 limit
    chunk_max_chars: int = 1500

    # Retrieval
    top_k: int = 5


settings = Settings()
