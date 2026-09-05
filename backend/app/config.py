"""Typed configuration foundation.

Environment variable names follow TECHNICAL_SPEC.md section 19.
Secrets use SecretStr so they never appear in logs, reprs, or error output.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    environment: str = "development"

    anthropic_api_key: SecretStr | None = None
    pantrypilot_llm_model: str | None = None
    recipeapi_io_api_key: SecretStr | None = None

    # Comma-separated list of allowed frontend origins. Empty by default:
    # CORS must be explicitly configured, never wildcarded, before any
    # origin is trusted.
    allowed_origins: list[str] = []

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def _parse_allowed_origins(cls, value: object) -> list[str]:
        if value is None or value == "":
            return []
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value  # type: ignore[return-value]

    @property
    def llm_configured(self) -> bool:
        return self.anthropic_api_key is not None and bool(self.pantrypilot_llm_model)

    @property
    def recipeapi_io_configured(self) -> bool:
        return self.recipeapi_io_api_key is not None


@lru_cache
def get_settings() -> Settings:
    return Settings()
