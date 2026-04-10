"""Factory configuration — loaded from environment variables via Pydantic Settings."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class FactorySettings(BaseSettings):
    """All runtime configuration for the Forge factory service."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Runtime ──────────────────────────────────────────────────
    environment: str = Field("development", description="development | staging | production")
    log_level: str = Field("INFO")
    human_review_required: bool = Field(True)
    max_generation_iterations: int = Field(5)
    evaluator_timeout_seconds: int = Field(600)

    # ── Database ─────────────────────────────────────────────────
    database_url: str = Field(
        "postgresql+asyncpg://forge:forge@localhost:5432/forge"
    )
    auto_init_db: bool = Field(False)

    # ── Redis / Celery ────────────────────────────────────────────
    redis_url: str = Field("redis://localhost:6379/0")

    # ── Object Storage ────────────────────────────────────────────
    s3_endpoint: str = Field("http://localhost:9000")
    s3_access_key: str = Field("minioadmin")
    s3_secret_key: str = Field("minioadmin")
    s3_bucket: str = Field("forge-packages")

    # ── Auth ──────────────────────────────────────────────────────
    factory_jwt_secret: str = Field("change-me")
    jwt_algorithm: str = Field("HS256")
    jwt_expiration_minutes: int = Field(60)

    # ── LLM routing (all via litellm) ─────────────────────────────
    anthropic_api_key: str = Field("")
    openai_api_key: str = Field("")
    openrouter_api_key: str = Field("")

    llm_primary_model: str = Field("openrouter/anthropic/claude-3.5-sonnet")
    llm_fallback_model: str = Field("openrouter/openai/gpt-4o")
    llm_reasoning_model: str = Field("openrouter/openai/o4-mini")
    llm_safety_model: str = Field("openrouter/anthropic/claude-3.5-haiku")
    llm_fast_model: str = Field("openrouter/anthropic/claude-3.5-haiku")
    embedding_model: str = Field("openai/text-embedding-3-large")

    # ── Observability ────────────────────────────────────────────
    langfuse_public_key: str = Field("")
    langfuse_secret_key: str = Field("")
    langfuse_host: str = Field("https://cloud.langfuse.com")

    # ── Tool integrations ─────────────────────────────────────────
    tavily_api_key: str = Field("")
    composio_api_key: str = Field("")
    infisical_client_id: str = Field("")
    infisical_client_secret: str = Field("")

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def celery_broker_url(self) -> str:
        return self.redis_url

    @property
    def celery_result_backend(self) -> str:
        return self.redis_url


@lru_cache(maxsize=1)
def get_settings() -> FactorySettings:
    """Return cached singleton settings instance."""
    return FactorySettings()
