from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "COMMONDEPTH API"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"
    database_url: str
    google_client_id: str | None = None
    onboarding_curated_usernames: str = ""

    media_storage_provider: str = "supabase"
    supabase_s3_endpoint: str
    supabase_s3_region: str = "eu-west-1"
    supabase_s3_access_key: str
    supabase_s3_secret_key: str
    supabase_s3_bucket: str = "common"

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[3] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
