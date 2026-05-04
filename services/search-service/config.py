from functools import lru_cache
from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8000
    opensearch_url: AnyHttpUrl = "http://opensearch:9200"
    opensearch_index: str = "anomaly-wiki-pages"
    internal_token: str = ""

    model_config = SettingsConfigDict(
        env_prefix="SEARCH_SERVICE_",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
