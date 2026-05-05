from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    encyclopedia_service_host: str = "0.0.0.0"
    encyclopedia_service_port: int = 8000
    database_url: str = "postgresql+asyncpg://admin:admin@db:5432/encyclopedia_db"
    rabbitmq_url: Optional[str] = None

    model_config = SettingsConfigDict(
        env_prefix="ENCYCLOPEDIA_SERVICE_",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
