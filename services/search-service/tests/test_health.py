from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from routes.health import router


def build_app(opensearch_client) -> FastAPI:
    app = FastAPI()
    app.state.opensearch = opensearch_client
    app.include_router(router)
    return app


async def test_health_returns_ok():
    app = build_app(MagicMock())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readiness_returns_ok_when_opensearch_ping_succeeds():
    fake_os = AsyncMock()
    fake_os.ping.return_value = True
    app = build_app(fake_os)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/readiness")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


async def test_readiness_returns_503_when_opensearch_ping_fails():
    fake_os = AsyncMock()
    fake_os.ping.return_value = False
    app = build_app(fake_os)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/readiness")
    assert response.status_code == 503
    assert response.json()["status"] == "unavailable"


async def test_readiness_returns_503_when_opensearch_ping_raises():
    fake_os = AsyncMock()
    fake_os.ping.side_effect = Exception("connection refused")
    app = build_app(fake_os)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/readiness")
    assert response.status_code == 503
    assert response.json()["status"] == "unavailable"
