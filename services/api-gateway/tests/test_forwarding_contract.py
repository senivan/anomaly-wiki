from datetime import timedelta

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient

from clients.http import forward_authenticated_request
from config import get_settings
from main import create_app
from security import AuthContext, get_auth_context
from tests.test_auth_validation import build_auth_keypair, build_jwks_service, issue_token


async def test_authenticated_forwarding_injects_gateway_identity_headers() -> None:
    private_key, jwk = build_auth_keypair()
    token = issue_token(private_key, role="Editor")

    upstream_app = FastAPI()

    @upstream_app.get("/pages")
    async def pages(request: Request) -> JSONResponse:
        return JSONResponse(
            {
                "user_id": request.headers.get("x-authenticated-user-id"),
                "email": request.headers.get("x-authenticated-user-email"),
                "role": request.headers.get("x-authenticated-user-role"),
                "source": request.headers.get("x-authenticated-source"),
                "request_id": request.headers.get("x-request-id"),
                "authorization": request.headers.get("authorization"),
            }
        )

    app = create_app(upstream_transport=ASGITransport(app=upstream_app))
    app.state.jwks_cache._keys = [jwk]
    app.state.jwks_cache._expires_at = 10**12

    router = APIRouter()

    @router.get("/proxy/pages")
    async def proxy_pages(
        request: Request,
        auth: AuthContext = Depends(get_auth_context),
    ):
        return await forward_authenticated_request(
            request,
            auth=auth,
            service="encyclopedia-service",
            upstream_base_url="http://encyclopedia-service:8000",
            upstream_path="/pages",
            settings=get_settings(),
        )

    app.include_router(router)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/proxy/pages",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Request-ID": "req-forward-1",
                "X-Authenticated-User-Id": "spoofed",
                "X-Authenticated-User-Role": "Admin",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] != "spoofed"
    assert body["email"] == "user@example.com"
    assert body["role"] == "Editor"
    assert body["source"] == "api-gateway"
    assert body["request_id"] == "req-forward-1"
    assert body["authorization"] is None


async def test_authenticated_forwarding_uses_single_attempt_on_upstream_failure() -> None:
    private_key, jwk = build_auth_keypair()
    token = issue_token(private_key, role="Researcher", expires_delta=timedelta(minutes=5))
    call_count = {"value": 0}

    upstream_app = FastAPI()

    @upstream_app.post("/drafts")
    async def drafts() -> JSONResponse:
        call_count["value"] += 1
        return JSONResponse(status_code=503, content={"detail": "temporarily unavailable"})

    app = create_app(upstream_transport=ASGITransport(app=upstream_app))
    app.state.jwks_cache._keys = [jwk]
    app.state.jwks_cache._expires_at = 10**12

    router = APIRouter()

    @router.post("/proxy/drafts")
    async def proxy_drafts(
        request: Request,
        auth: AuthContext = Depends(get_auth_context),
    ):
        return await forward_authenticated_request(
            request,
            auth=auth,
            service="encyclopedia-service",
            upstream_base_url="http://encyclopedia-service:8000",
            upstream_path="/drafts",
            settings=get_settings(),
        )

    app.include_router(router)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/proxy/drafts",
            headers={"Authorization": f"Bearer {token}"},
            json={"title": "draft"},
        )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "upstream_server_error"
    assert call_count["value"] == 1


async def test_jwks_refreshes_from_auth_service_when_cache_is_empty() -> None:
    private_key, jwk = build_auth_keypair()
    token = issue_token(private_key)

    upstream_app = FastAPI()

    @upstream_app.get("/search")
    async def search(request: Request) -> JSONResponse:
        return JSONResponse(
            {
                "user_id": request.headers.get("x-authenticated-user-id"),
                "role": request.headers.get("x-authenticated-user-role"),
            }
        )

    gateway_app = create_app(upstream_transport=ASGITransport(app=build_jwks_service(jwk)))
    router = APIRouter()

    @router.get("/proxy/search")
    async def proxy_search(
        request: Request,
        auth: AuthContext = Depends(get_auth_context),
    ):
        request.app.state.upstream_transport = ASGITransport(app=upstream_app)
        return await forward_authenticated_request(
            request,
            auth=auth,
            service="search-service",
            upstream_base_url="http://search-service:8000",
            upstream_path="/search",
            settings=get_settings(),
        )

    gateway_app.include_router(router)

    async with AsyncClient(transport=ASGITransport(app=gateway_app), base_url="http://test") as client:
        response = await client.get(
            "/proxy/search",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "user_id": response.json()["user_id"],
        "role": "Researcher",
    }
