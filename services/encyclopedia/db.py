from functools import lru_cache
from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from config import get_settings


@lru_cache
def get_engine() -> AsyncEngine:
    settings = get_settings()
    engine_kwargs: dict[str, object] = {}
    if settings.database_url.startswith("sqlite"):
        from sqlalchemy.pool import StaticPool

        engine_kwargs = {
            "poolclass": StaticPool,
            "connect_args": {"check_same_thread": False},
        }

    return create_async_engine(settings.database_url, **engine_kwargs)


@lru_cache
def get_session_maker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with get_session_maker()() as session:
        yield session


async def check_database_connection() -> None:
    async with get_engine().connect() as connection:
        await connection.execute(text("SELECT 1"))


async def dispose_engine() -> None:
    await get_engine().dispose()


def reset_database_state() -> None:
    get_session_maker.cache_clear()
    get_engine.cache_clear()
