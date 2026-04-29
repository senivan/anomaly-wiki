from functools import lru_cache

from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    gateway_host: str = "0.0.0.0"
    gateway_port: int = 8000

    researcher_auth_base_url: AnyHttpUrl = "http://researcher-auth-service:8000"
    encyclopedia_base_url: AnyHttpUrl = "http://encyclopedia-service:8000"
    media_service_base_url: AnyHttpUrl = "http://media-service:8000"
    search_service_base_url: AnyHttpUrl = "http://search-service:8000"

    model_config = SettingsConfigDict(
        env_prefix="API_GATEWAY_",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
