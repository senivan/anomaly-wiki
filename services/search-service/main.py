import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from config import get_settings
from opensearch import create_opensearch_client
from routes.health import router as health_router
from routes.search import router as search_router

logger = logging.getLogger(__name__)

_INDEX_MAPPINGS = {
    "mappings": {
        "properties": {
            "page_id":      {"type": "keyword"},
            "slug":         {"type": "keyword"},
            "type":         {"type": "keyword"},
            "status":       {"type": "keyword"},
            "visibility":   {"type": "keyword"},
            "tags":         {"type": "keyword"},
            "title":        {"type": "text"},
            "summary":      {"type": "text"},
            "content_text": {"type": "text"},
            "aliases":      {"type": "text"},
        }
    }
}


def create_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        client = create_opensearch_client(settings)
        app.state.opensearch = client
        try:
            reachable = await client.ping()
            if not reachable:
                logger.warning(
                    "OpenSearch at %s is not reachable at startup", settings.opensearch_url
                )
        except Exception as exc:
            logger.warning("OpenSearch startup ping failed: %s: %s", type(exc).__name__, exc)
        else:
            try:
                exists = await client.indices.exists(index=settings.opensearch_index)
                if not exists:
                    await client.indices.create(
                        index=settings.opensearch_index, body=_INDEX_MAPPINGS
                    )
                    logger.info("Created OpenSearch index %s", settings.opensearch_index)
            except Exception as exc:
                logger.warning(
                    "Could not ensure index %s exists: %s: %s",
                    settings.opensearch_index,
                    type(exc).__name__,
                    exc,
                )
        try:
            yield
        finally:
            await client.close()

    app = FastAPI(
        title="Search Service",
        description="Full-text search over the Anomaly Wiki encyclopedia.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(health_router)
    app.include_router(search_router)
    return app


app = create_app()
