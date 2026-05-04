from contextlib import asynccontextmanager

from fastapi import FastAPI

from config import get_settings
from db import dispose_engine, get_engine
from models import Base
from routes.health import router as health_router
from routes.media import router as media_router
from storage import ObjectStorage, build_object_storage


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with get_engine().begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield
    await dispose_engine()


def create_app(*, storage_backend: ObjectStorage | None = None) -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Media Service",
        description="Source of truth for binary media assets and metadata.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.storage_backend = storage_backend or build_object_storage(settings)
    app.include_router(health_router)
    app.include_router(media_router)
    return app


app = create_app()
