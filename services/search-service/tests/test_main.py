from unittest.mock import AsyncMock, patch
from httpx import ASGITransport, AsyncClient
from main import create_app


async def test_app_has_search_route():
    fake_os = AsyncMock()
    fake_os.search.return_value = {
        "hits": {"total": {"value": 0}, "hits": []}
    }
    with patch("main.create_opensearch_client", return_value=fake_os):
        app = create_app()
    app.state.opensearch = fake_os
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/search?q=test")
    assert response.status_code == 200


async def test_app_has_health_route():
    fake_os = AsyncMock()
    with patch("main.create_opensearch_client", return_value=fake_os):
        app = create_app()
    app.state.opensearch = fake_os
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200


def test_startup_logs_warning_when_opensearch_unreachable(caplog):
    import logging
    from unittest.mock import AsyncMock, patch
    from starlette.testclient import TestClient

    fake_client = AsyncMock()
    fake_client.ping.return_value = False

    with patch("main.create_opensearch_client", return_value=fake_client):
        with caplog.at_level(logging.WARNING, logger="main"):
            with TestClient(create_app()) as client:
                response = client.get("/health")

    assert response.status_code == 200  # service still starts
    assert any("not reachable" in r.message.lower() for r in caplog.records)
