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

    # Graph (Neo4j)
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: SecretStr = SecretStr("")
    graph_max_hops: int = 2
    graph_max_paths: int = 50
    extraction_batch_chars: int = 12_000  # chunk text per extraction LLM call
    extraction_max_tokens: int = 16_000
    extraction_min_confidence: float = 0.5  # drop relationships the LLM is unsure of

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

    # Document analysis (PRD 7.2). Starting values; tuned against the eval set.
    sample_min_sections: int = 5
    sample_max_sections: int = 10
    sample_max_chars: int = 24_000  # cap on text sent to the LLM for the sample
    sample_max_tokens: int = 16_000  # reasoning + JSON; 8K ran out on a dense spec
    sample_max_items: int = 40  # entities/relationships asked for: enough to estimate density
    many_relationships_density: float = 1.5  # relationships per entity in the sample
    many_relationships_cross_ref_rate: float = 2.0  # per 1,000 words
    many_relationships_phrase_rate: float = 3.0  # per 1,000 words
    small_plain_max_pages: int = 10
    small_plain_max_identifier_density: float = 1.0  # per 1,000 words
    small_plain_max_table_share: float = 0.05
    exact_terms_identifier_density: float = 3.0  # suggest the exact_terms intent above this
    words_per_page: int = 500  # page estimate for formats without pages

    # Query intelligence and self-correction (PRD 7.5, 7.6)
    classifier_llm_fallback: bool = True  # ask the LLM only when rules are unsure
    classifier_max_tokens: int = 4000
    relevance_threshold: float = 0.15  # reranker-based relevance below this -> rewrite
    max_retries: int = 2  # query rewrites before giving up
    rewrite_max_tokens: int = 4000
    grounding_max_tokens: int = 6000
    grounding_enabled: bool = True

    # Retrieval
    top_k: int = 5  # chunks given to the LLM
    candidate_k: int = 20  # chunks each retriever returns before fusion and reranking
    rrf_k: int = 60  # reciprocal rank fusion constant (standard value)


settings = Settings()
if not settings.jwt_secret.get_secret_value():
    settings.jwt_secret = SecretStr(secrets.token_urlsafe(32))
