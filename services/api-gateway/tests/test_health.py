import json
import logging

import httpx
from fastapi import APIRouter
from httpx import ASGITransport, AsyncClient

from errors import GatewayUpstreamResponseError
from main import create_app


async def test_healthcheck() -> None:
    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readiness_exposes_downstream_configuration() -> None:
    app = create_app()
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


async def test_request_id_header_is_propagated() -> None:
    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/health", headers={"X-Request-ID": "req-123"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "req-123"


async def test_cors_is_explicitly_enabled() -> None:
    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.options(
            "/health",
            headers={
                "Origin": "http://example.com",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"


async def test_timeout_errors_are_normalized() -> None:
    router = APIRouter()

    @router.get("/timeout")
    async def timeout_route() -> None:
        raise httpx.ReadTimeout("timed out")

    app = create_app()
    app.include_router(router)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/timeout")

    assert response.status_code == 504
    assert response.json()["error"]["code"] == "upstream_timeout"


async def test_connect_errors_are_normalized() -> None:
    router = APIRouter()

    @router.get("/connect-error")
    async def connect_error_route() -> None:
        raise httpx.ConnectError("connection refused")

    app = create_app()
    app.include_router(router)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/connect-error")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "upstream_unavailable"


async def test_upstream_4xx_is_normalized_without_changing_status() -> None:
    router = APIRouter()

    @router.get("/upstream-401")
    async def upstream_401_route() -> None:
        raise GatewayUpstreamResponseError(
            service="researcher-auth-service",
            status_code=401,
            body={"detail": "bad credentials"},
        )

    app = create_app()
    app.include_router(router)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/upstream-401")

    assert response.status_code == 401
    assert response.json() == {
        "error": {
            "code": "upstream_client_error",
            "message": "Upstream service returned an error response.",
            "request_id": response.headers["X-Request-ID"],
            "details": {
                "service": "researcher-auth-service",
                "upstream_status": 401,
                "upstream_body": {"detail": "bad credentials"},
            },
        }
    }


async def test_request_logging_includes_request_metadata(caplog) -> None:
    app = create_app()
    caplog.set_level(logging.INFO, logger="api_gateway")

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/health", headers={"X-Request-ID": "log-123"})

    assert response.status_code == 200
    payload = json.loads(caplog.records[-1].message)
    assert payload["event"] == "request.complete"
    assert payload["request_id"] == "log-123"
    assert payload["method"] == "GET"
    assert payload["path"] == "/health"
    assert payload["status_code"] == 200
