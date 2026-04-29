from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import APIRouter, Depends, FastAPI, Request
from httpx import ASGITransport, AsyncClient

from main import create_app
from security import AuthContext, jwk_from_public_numbers, require_role, get_auth_context


def build_auth_keypair() -> tuple[object, dict[str, str]]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_numbers = private_key.public_key().public_numbers()
    jwk = jwk_from_public_numbers(public_numbers.n, public_numbers.e)
    return private_key, jwk


def issue_token(
    private_key,
    *,
    role: str = "Researcher",
    audience: str = "fastapi-users:auth",
    expires_delta: timedelta = timedelta(minutes=5),
    kid: str | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    claims = {
        "sub": str(uuid4()),
        "email": "user@example.com",
        "role": role,
        "aud": audience,
        "iat": now,
        "exp": now + expires_delta,
    }
    headers = {"kid": kid} if kid is not None else None
    return jwt.encode(claims, private_key, algorithm="RS256", headers=headers)


def build_jwks_service(jwk: dict[str, str]) -> FastAPI:
    app = FastAPI()

    @app.get("/auth/jwks")
    async def jwks() -> dict[str, list[dict[str, str]]]:
        return {"keys": [jwk]}

    return app


def add_protected_routes(app: FastAPI) -> None:
    router = APIRouter()

    @router.get("/protected")
    async def protected(auth: AuthContext = Depends(get_auth_context)) -> dict[str, str | None]:
        return {
            "sub": auth.subject,
            "email": auth.email,
            "role": auth.role,
        }

    @router.get("/editor-only")
    async def editor_only(
        auth: AuthContext = Depends(require_role("Editor", "Admin")),
    ) -> dict[str, str | None]:
        return {
            "sub": auth.subject,
            "email": auth.email,
            "role": auth.role,
        }

    @router.get("/auth-state")
    async def auth_state(
        request: Request,
        auth: AuthContext = Depends(get_auth_context),
    ) -> dict[str, str | None]:
        state_auth = request.state.auth
        return {
            "sub": state_auth.subject,
            "email": state_auth.email,
            "role": state_auth.role,
            "resolved_sub": auth.subject,
        }

    app.include_router(router)


async def test_missing_token_returns_401() -> None:
    private_key, jwk = build_auth_keypair()
    app = create_app(upstream_transport=ASGITransport(app=build_jwks_service(jwk)))
    add_protected_routes(app)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/protected")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["error"]["code"] == "missing_bearer_token"


async def test_invalid_header_returns_401() -> None:
    private_key, jwk = build_auth_keypair()
    app = create_app(upstream_transport=ASGITransport(app=build_jwks_service(jwk)))
    add_protected_routes(app)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/protected", headers={"Authorization": "Token abc"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_authorization_header"


async def test_valid_token_populates_auth_context() -> None:
    private_key, jwk = build_auth_keypair()
    token = issue_token(private_key, role="Researcher")
    app = create_app(upstream_transport=ASGITransport(app=build_jwks_service(jwk)))
    add_protected_routes(app)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/protected", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["email"] == "user@example.com"
    assert response.json()["role"] == "Researcher"


async def test_valid_token_attaches_auth_context_to_request_state() -> None:
    private_key, jwk = build_auth_keypair()
    token = issue_token(private_key, role="Researcher")
    app = create_app(upstream_transport=ASGITransport(app=build_jwks_service(jwk)))
    add_protected_routes(app)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/auth-state", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["email"] == "user@example.com"
    assert response.json()["role"] == "Researcher"
    assert response.json()["sub"] == response.json()["resolved_sub"]


async def test_expired_token_returns_401() -> None:
    private_key, jwk = build_auth_keypair()
    token = issue_token(private_key, expires_delta=timedelta(minutes=-5))
    app = create_app(upstream_transport=ASGITransport(app=build_jwks_service(jwk)))
    add_protected_routes(app)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/protected", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_token"
    assert response.json()["error"]["details"]["reason"] == "ExpiredSignatureError"


async def test_wrong_audience_returns_401() -> None:
    private_key, jwk = build_auth_keypair()
    token = issue_token(private_key, audience="wrong-audience")
    app = create_app(upstream_transport=ASGITransport(app=build_jwks_service(jwk)))
    add_protected_routes(app)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/protected", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.json()["error"]["details"]["reason"] == "InvalidAudienceError"


async def test_insufficient_role_returns_403() -> None:
    private_key, jwk = build_auth_keypair()
    token = issue_token(private_key, role="Researcher")
    app = create_app(upstream_transport=ASGITransport(app=build_jwks_service(jwk)))
    add_protected_routes(app)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/editor-only", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


async def test_editor_role_is_allowed() -> None:
    private_key, jwk = build_auth_keypair()
    token = issue_token(private_key, role="Editor")
    app = create_app(upstream_transport=ASGITransport(app=build_jwks_service(jwk)))
    add_protected_routes(app)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/editor-only", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["role"] == "Editor"


async def test_missing_kid_works_with_single_jwks_key() -> None:
    private_key, jwk = build_auth_keypair()
    token = issue_token(private_key, kid=None)
    app = create_app(upstream_transport=ASGITransport(app=build_jwks_service(jwk)))
    add_protected_routes(app)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/protected", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
