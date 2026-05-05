from contextlib import asynccontextmanager

from fastapi import FastAPI

from config import get_settings
from db import dispose_engine, get_engine
from models import Base
from publisher import NoopPublisher, connect_publisher
from routes.health import router as health_router
from routes.pages import router as pages_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with get_engine().begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    settings = get_settings()
    rabbitmq_connection, publisher = await connect_publisher(settings.rabbitmq_url)
    app.state.publisher = publisher
    try:
        yield
    finally:
        if rabbitmq_connection:
            await rabbitmq_connection.close()
        await dispose_engine()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Encyclopedia Service",
        description="Canonical source of truth for encyclopedia pages and revision history.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.publisher = NoopPublisher()
    app.include_router(health_router)
    app.include_router(pages_router)
    return app


app = create_app()
