from httpx import ASGITransport, AsyncClient

from config import get_settings
from db import reset_database_state
from main import create_app


def reset_caches() -> None:
    get_settings.cache_clear()
    reset_database_state()


async def test_healthcheck() -> None:
    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readiness_checks_database(monkeypatch) -> None:
    monkeypatch.setenv("ENCYCLOPEDIA_SERVICE_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    reset_caches()
    app = create_app()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "services": {"database": "ok"},
        "database_url": "sqlite+aiosqlite:///:memory:",
    }

    reset_caches()
