"""Runtime-local settings shared by packaged employee code."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class RuntimeSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    llm_primary_model: str = Field("openrouter/anthropic/claude-3.5-sonnet")
    llm_fallback_model: str = Field("openrouter/openai/gpt-4o")
    llm_reasoning_model: str = Field("openrouter/openai/o4-mini")
    llm_safety_model: str = Field("openrouter/anthropic/claude-3.5-haiku")
    llm_fast_model: str = Field("openrouter/anthropic/claude-3.5-haiku")
    embedding_model: str = Field("openai/text-embedding-3-large")
    langfuse_enabled: bool = Field(False)


@lru_cache(maxsize=1)
def get_settings() -> RuntimeSettings:
    return RuntimeSettings()
