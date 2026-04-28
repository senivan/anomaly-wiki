import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql+asyncpg://admin:admin@localhost:5432/anomaly_wiki")

engine_kwargs = {}
if DATABASE_URL.startswith("sqlite"):
    from sqlalchemy.pool import StaticPool
    engine_kwargs = {
        "poolclass": StaticPool,
        "connect_args": {"check_same_thread": False},
    }

engine = create_async_engine(DATABASE_URL, **engine_kwargs)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)

async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session
