"""Runtime configuration, loaded from .env."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All environment-driven config lives here."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Google AI
    google_api_key: str = ""
    gemini_text_model: str = "gemini-3.5-flash"
    gemini_vision_model: str = "gemini-3.5-flash"
    gemini_image_model: str = "gemini-2.5-flash-image"

    # Meta Ad Library
    meta_access_token: str = ""
    use_meta_stub: bool = True

    # Data source dispatcher — controls IngestAgent backend selection.
    # Valid values: "meta_stub" | "bq_political" | "meta_live" | "bq_kaggle"
    data_source: str = "meta_stub"

    # BigQuery tables (used when data_source is bq_*).
    bq_political_table: str = "bigquery-public-data.google_political_ads.creative_stats"
    bq_kaggle_table: str = ""
    bq_limit_per_brand: int = 50

    # GCP / Firebase (optional in MVP)
    gcp_project_id: str = ""
    firestore_collection: str = "adintel_analyses"
    firebase_storage_bucket: str = ""

    # App
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached singleton."""
    return Settings()
