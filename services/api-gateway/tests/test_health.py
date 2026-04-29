from httpx import ASGITransport, AsyncClient

from main import app


async def test_healthcheck() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readiness_exposes_downstream_configuration() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "services": {
            "researcher_auth_service": "http://researcher-auth-service:8000/",
            "encyclopedia_service": "http://encyclopedia-service:8000/",
            "media_service": "http://media-service:8000/",
            "search_service": "http://search-service:8000/",
        },
    }
