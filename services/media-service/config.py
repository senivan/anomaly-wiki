from functools import lru_cache
from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    media_service_host: str = "0.0.0.0"
    media_service_port: int = 8000
    database_url: str = "postgresql+asyncpg://admin:admin@db:5432/media_db"

    object_storage_endpoint: str = "minio:9000"
    object_storage_access_key: str = "admin"
    object_storage_secret_key: str = "admin123"
    object_storage_bucket: str = "anomaly-media"
    object_storage_secure: bool = False
    signed_url_ttl_seconds: int = 900

    # When set, presigned download URLs are rewritten to use this base URL
    # instead of the internal storage endpoint (e.g. "http://localhost:9000").
    public_storage_base_url: Optional[str] = None

    # Maximum allowed upload size in bytes (default: 50 MB).
    max_upload_bytes: int = 52_428_800

    @field_validator("signed_url_ttl_seconds")
    @classmethod
    def _ttl_must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("signed_url_ttl_seconds must be a positive integer")
        return v

    @field_validator("max_upload_bytes")
    @classmethod
    def _max_upload_must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("max_upload_bytes must be a positive integer")
        return v

    model_config = SettingsConfigDict(
        env_prefix="MEDIA_SERVICE_",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
