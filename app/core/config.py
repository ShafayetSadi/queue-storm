"""Runtime configuration, sourced from environment variables.

All LLM settings are optional: with ``USE_LLM=false`` (or no API key) the
service runs the deterministic engine only, with no network dependency.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Service
    port: int = 8000
    log_complaint_text: bool = False  # keep PII out of logs by default

    # LLM (OpenRouter, OpenAI-compatible). ON by default per design.
    use_llm: bool = True
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    model_name: str = "google/gemini-2.5-flash-lite"
    llm_timeout_seconds: float = 4.0
    llm_max_retries: int = 0
    # Optional OpenRouter attribution headers (harmless if blank).
    openrouter_referer: str = "https://github.com/queuestorm-investigator"
    openrouter_title: str = "QueueStorm Investigator"

    @property
    def llm_enabled(self) -> bool:
        """LLM is only truly usable when enabled AND a key is present."""
        return self.use_llm and bool(self.openrouter_api_key.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
