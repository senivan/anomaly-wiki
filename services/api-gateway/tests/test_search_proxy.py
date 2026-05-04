from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient

from config import get_settings
from main import create_app
from tests.test_auth_validation import build_auth_keypair, issue_token


def reset_settings() -> None:
    get_settings.cache_clear()


def build_upstream_search_app() -> FastAPI:
    app = FastAPI()

    @app.get("/search")
    async def search(request: Request) -> JSONResponse:
        return JSONResponse({
            "source": request.headers.get("x-authenticated-source"),
            "role": request.headers.get("x-authenticated-user-role"),
            "user_id": request.headers.get("x-authenticated-user-id"),
            "internal_token": request.headers.get("x-internal-token"),
            "total": 0,
            "hits": [],
        })

    @app.get("/search/suggest")
    async def suggest(request: Request) -> JSONResponse:
        return JSONResponse({
            "source": request.headers.get("x-authenticated-source"),
            "suggestions": [],
        })

    return app


async def test_search_proxy_forwards_without_auth_headers_for_unauthenticated_request():
    upstream = build_upstream_search_app()
    app = create_app(upstream_transport=ASGITransport(app=upstream))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/search?q=fire")

    assert response.status_code == 200
    body = response.json()
    assert body["source"] is None


async def test_search_proxy_injects_auth_headers_for_authenticated_request():
    private_key, jwk = build_auth_keypair()
    token = issue_token(private_key, role="Researcher")

    upstream = build_upstream_search_app()
    app = create_app(upstream_transport=ASGITransport(app=upstream))
    app.state.jwks_cache._keys = [jwk]
    app.state.jwks_cache._expires_at = 10**12

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/search?q=fire",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "api-gateway"
    assert body["role"] == "Researcher"
    assert body["user_id"] is not None
    assert body["internal_token"] is None


async def test_search_proxy_replaces_client_internal_token(monkeypatch):
    monkeypatch.setenv("API_GATEWAY_SEARCH_INTERNAL_TOKEN", "gateway-secret")
    reset_settings()
    private_key, jwk = build_auth_keypair()
    token = issue_token(private_key, role="Editor")

    upstream = build_upstream_search_app()
    app = create_app(upstream_transport=ASGITransport(app=upstream))
    app.state.jwks_cache._keys = [jwk]
    app.state.jwks_cache._expires_at = 10**12

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/search?q=fire",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Internal-Token": "client-secret",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "api-gateway"
    assert body["role"] == "Editor"
    assert body["internal_token"] == "gateway-secret"
    reset_settings()


async def test_search_proxy_strips_client_internal_token_for_public_request():
    upstream = build_upstream_search_app()
    app = create_app(upstream_transport=ASGITransport(app=upstream))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/search?q=fire",
            headers={"X-Internal-Token": "client-secret"},
        )

    assert response.status_code == 200
    assert response.json()["internal_token"] is None


async def test_suggest_proxy_forwards_without_auth_for_unauthenticated_request():
    upstream = build_upstream_search_app()
    app = create_app(upstream_transport=ASGITransport(app=upstream))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/search/suggest?q=fir")

    assert response.status_code == 200
    body = response.json()
    assert body["source"] is None


async def test_search_proxy_returns_401_for_invalid_token():
    """An invalid bearer token must return 401, not silently degrade to anonymous."""
    upstream = build_upstream_search_app()
    app = create_app(upstream_transport=ASGITransport(app=upstream))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/search?q=fire",
            headers={"Authorization": "Bearer thisisnotavalidtoken"},
        )

    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"
    assert response.json()["error"]["code"] == "invalid_token"
