from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient

from main import create_app


def build_auth_service() -> FastAPI:
    app = FastAPI()

    @app.post("/auth/register")
    async def register() -> JSONResponse:
        return JSONResponse(
            status_code=201,
            content={"user_id": "user-1"},
            headers={"cache-control": "no-store"},
        )

    @app.post("/auth/login")
    async def login() -> JSONResponse:
        return JSONResponse(
            status_code=200,
            content={"access_token": "token-123", "token_type": "bearer"},
            headers={"cache-control": "no-store"},
        )

    @app.post("/auth/logout")
    async def logout() -> JSONResponse:
        return JSONResponse(status_code=204, content=None)

    @app.get("/auth/jwks")
    async def jwks() -> JSONResponse:
        return JSONResponse(status_code=200, content={"keys": [{"kid": "default"}]})

    return app


async def test_register_is_proxied_to_auth_service() -> None:
    app = create_app(upstream_transport=ASGITransport(app=build_auth_service()))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/auth/register", json={"email": "user@example.com"})

    assert response.status_code == 201
    assert response.json() == {"user_id": "user-1"}
    assert response.headers["cache-control"] == "no-store"


async def test_login_is_proxied_with_form_body() -> None:
    app = create_app(upstream_transport=ASGITransport(app=build_auth_service()))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/auth/login",
            data={"username": "user@example.com", "password": "secret"},
            headers={"X-Request-ID": "auth-login-1"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "access_token": "token-123",
        "token_type": "bearer",
    }
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["X-Request-ID"] == "auth-login-1"


async def test_generated_request_id_is_forwarded_upstream() -> None:
    upstream_app = FastAPI()

    @upstream_app.post("/auth/login")
    async def login(request: Request) -> JSONResponse:
        return JSONResponse(
            status_code=200,
            content={"request_id": request.headers.get("x-request-id")},
        )

    app = create_app(upstream_transport=ASGITransport(app=upstream_app))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/auth/login", data={"username": "user@example.com"})

    assert response.status_code == 200
    assert response.json()["request_id"] == response.headers["X-Request-ID"]


async def test_jwks_is_proxied_to_auth_service() -> None:
    app = create_app(upstream_transport=ASGITransport(app=build_auth_service()))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/auth/jwks")

    assert response.status_code == 200
    assert response.json() == {"keys": [{"kid": "default"}]}


async def test_upstream_auth_error_preserves_status_and_safe_headers() -> None:
    upstream_app = FastAPI()

    @upstream_app.post("/auth/login")
    async def login_fail() -> JSONResponse:
        return JSONResponse(
            status_code=401,
            content={"detail": "bad credentials"},
            headers={
                "cache-control": "no-store",
                "www-authenticate": "Bearer",
            },
        )

    app = create_app(upstream_transport=ASGITransport(app=upstream_app))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/auth/login", data={"username": "user@example.com"})

    assert response.status_code == 401
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["error"]["code"] == "upstream_client_error"
    assert response.json()["error"]["details"]["service"] == "researcher-auth-service"


async def test_bad_credentials_error_is_exposed_as_unauthorized() -> None:
    upstream_app = FastAPI()

    @upstream_app.post("/auth/login")
    async def login_fail() -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"detail": "LOGIN_BAD_CREDENTIALS"},
            headers={"cache-control": "no-store"},
        )

    app = create_app(upstream_transport=ASGITransport(app=upstream_app))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/auth/login", data={"username": "user@example.com"})

    assert response.status_code == 401
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["error"]["details"]["upstream_status"] == 401
    assert response.json()["error"]["details"]["upstream_body"] == {"detail": "LOGIN_BAD_CREDENTIALS"}
