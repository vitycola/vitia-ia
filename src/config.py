from functools import lru_cache

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

MAX_IMAGE_BYTES = 4 * 1024 * 1024  # 4 MiB


class Settings(BaseSettings):
    app_name: str = "vitia-ia"
    allowed_origins: list[str] = []
    log_level: str = "INFO"
    supabase_jwks_url: str = ""

    # Supabase settings
    supabase_url: str = ""
    supabase_anon_key: SecretStr = SecretStr("")

    # LLM settings
    llm_provider: str = "anthropic"
    anthropic_api_key: SecretStr | None = None
    anthropic_model: str = "claude-opus-4-8"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def _require_supabase_vars(self) -> "Settings":
        if not self.supabase_url:
            raise ValueError("SUPABASE_URL is required but not set.")
        if not self.supabase_anon_key.get_secret_value():
            raise ValueError("SUPABASE_ANON_KEY is required but not set.")
        if not self.supabase_jwks_url:
            raise ValueError("SUPABASE_JWKS_URL is required but not set.")
        return self

    @model_validator(mode="after")
    def _require_active_key(self) -> "Settings":
        required: dict[str, SecretStr | None] = {
            "anthropic": self.anthropic_api_key,
        }
        if self.llm_provider in required and required[self.llm_provider] is None:
            raise ValueError(
                f"{self.llm_provider} provider is active but its API key is missing. "
                f"Set ANTHROPIC_API_KEY in your environment."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
