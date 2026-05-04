from functools import lru_cache

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

    model_config = SettingsConfigDict(
        env_prefix="MEDIA_SERVICE_",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
