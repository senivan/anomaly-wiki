from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    rabbitmq_url: str = "amqp://guest:guest@rabbitmq:5672/"
    opensearch_url: str = "http://opensearch:9200"
    opensearch_index: str = "anomaly-wiki-pages"
    encyclopedia_url: str = "http://encyclopedia-service:8000"
    exchange_name: str = "encyclopedia.events"
    queue_name: str = "search-indexer"

    model_config = SettingsConfigDict(
        env_prefix="SEARCH_INDEXER_",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
