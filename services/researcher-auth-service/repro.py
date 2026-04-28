import asyncio
import os
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["AUTH_PRIVATE_KEY_PATH"] = "test_key.pem"

from main import app
from httpx import AsyncClient, ASGITransport

async def run():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # This should trigger lifespan and create tables
        response = await ac.get("/auth/jwks")
        print(f"JWKS: {response.status_code}")
        
        # Now try to check if user table exists
        from db import engine
        from sqlalchemy import text
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='user';"))
            row = result.fetchone()
            print(f"User table exists: {row is not None}")

if __name__ == "__main__":
    asyncio.run(run())
    if os.path.exists("test_key.pem"):
        os.remove("test_key.pem")
