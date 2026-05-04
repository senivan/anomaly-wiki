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


async def test_no_cors_headers_on_search_response():
    """Internal service must not advertise permissive CORS."""
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.options(
            "/search",
            headers={"Origin": "http://evil.example.com", "Access-Control-Request-Method": "GET"},
        )
    assert "access-control-allow-origin" not in response.headers


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


async def test_lifespan_creates_index_when_missing():
    """Startup must create the OpenSearch index if it does not already exist."""
    fake_os = AsyncMock()
    fake_os.ping.return_value = True
    fake_os.indices = AsyncMock()
    fake_os.indices.exists.return_value = False
    fake_os.indices.create.return_value = {"acknowledged": True}

    with patch("main.create_opensearch_client", return_value=fake_os):
        app = create_app()
        async with app.router.lifespan_context(app):
            pass

    fake_os.indices.exists.assert_awaited_once()
    fake_os.indices.create.assert_awaited_once()


async def test_lifespan_skips_index_creation_when_index_exists():
    """Startup must not attempt to recreate an existing index."""
    fake_os = AsyncMock()
    fake_os.ping.return_value = True
    fake_os.indices = AsyncMock()
    fake_os.indices.exists.return_value = True

    with patch("main.create_opensearch_client", return_value=fake_os):
        app = create_app()
        async with app.router.lifespan_context(app):
            pass

    fake_os.indices.exists.assert_awaited_once()
    fake_os.indices.create.assert_not_awaited()
