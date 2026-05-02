from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient

from main import create_app
from tests.test_auth_validation import build_auth_keypair, issue_token


def build_upstream_search_app() -> FastAPI:
    app = FastAPI()

    @app.get("/search")
    async def search(request: Request) -> JSONResponse:
        return JSONResponse({
            "source": request.headers.get("x-authenticated-source"),
            "role": request.headers.get("x-authenticated-user-role"),
            "user_id": request.headers.get("x-authenticated-user-id"),
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


async def test_suggest_proxy_forwards_without_auth_for_unauthenticated_request():
    upstream = build_upstream_search_app()
    app = create_app(upstream_transport=ASGITransport(app=upstream))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/search/suggest?q=fir")

    assert response.status_code == 200
    body = response.json()
    assert body["source"] is None
