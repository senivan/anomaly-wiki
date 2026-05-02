from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from opensearch import create_opensearch_client
from routes.health import router as health_router
from routes.search import router as search_router


def create_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        client = create_opensearch_client(settings)
        app.state.opensearch = client
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
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET"],
        allow_headers=["*"],
    )
    app.include_router(health_router)
    app.include_router(search_router)
    return app


app = create_app()
