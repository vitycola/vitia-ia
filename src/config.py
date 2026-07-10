from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "vitia-ia"
    allowed_origins: list[str] = []
    log_level: str = "INFO"
    supabase_jwks_url: str = "https://uynyfvvhlesklvdwyxlv.supabase.co/auth/v1/.well-known/jwks.json"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
