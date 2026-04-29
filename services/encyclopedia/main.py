from contextlib import asynccontextmanager

from fastapi import FastAPI

from db import dispose_engine, get_engine
from routes.health import router as health_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_engine()
    yield
    await dispose_engine()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Encyclopedia Service",
        description="Canonical source of truth for encyclopedia pages and revision history.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(health_router)
    return app


app = create_app()
