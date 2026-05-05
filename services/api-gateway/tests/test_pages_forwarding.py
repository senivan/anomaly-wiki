from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient

from main import create_app
from tests.test_auth_validation import build_auth_keypair, issue_token


def build_upstream_pages_app() -> FastAPI:
    app = FastAPI()

    @app.get("/pages/{page_id}")
    async def get_page(page_id: str, request: Request) -> JSONResponse:
        return JSONResponse(
            {
                "page_id": page_id,
                "source": request.headers.get("x-authenticated-source"),
                "role": request.headers.get("x-authenticated-user-role"),
                "authorization": request.headers.get("authorization"),
            }
        )

    @app.get("/pages/{page_id}/revisions")
    async def list_revisions(page_id: str) -> JSONResponse:
        return JSONResponse({"page_id": page_id, "revisions": []})

    @app.get("/pages/{page_id}/revisions/{revision_id}")
    async def get_revision(page_id: str, revision_id: str) -> JSONResponse:
        return JSONResponse({"page_id": page_id, "revision_id": revision_id})

    @app.post("/pages")
    async def create_page(request: Request) -> JSONResponse:
        return JSONResponse(
            status_code=201,
            content={
                "source": request.headers.get("x-authenticated-source"),
                "user_id": request.headers.get("x-authenticated-user-id"),
                "email": request.headers.get("x-authenticated-user-email"),
                "role": request.headers.get("x-authenticated-user-role"),
                "authorization": request.headers.get("authorization"),
            },
        )

    @app.post("/pages/{page_id}/drafts")
    async def create_draft(page_id: str, request: Request) -> JSONResponse:
        payload = await request.json()
        return JSONResponse(
            status_code=201,
            content={
                "page_id": page_id,
                "title": payload.get("title"),
                "source": request.headers.get("x-authenticated-source"),
                "role": request.headers.get("x-authenticated-user-role"),
            },
        )

    @app.put("/pages/{page_id}/metadata")
    async def update_metadata(page_id: str, request: Request) -> JSONResponse:
        return JSONResponse(
            {
                "page_id": page_id,
                "source": request.headers.get("x-authenticated-source"),
            }
        )

    @app.post("/pages/{page_id}/publish")
    async def publish(page_id: str) -> JSONResponse:
        return JSONResponse({"page_id": page_id, "action": "publish"})

    @app.post("/pages/{page_id}/revert")
    async def revert(page_id: str) -> JSONResponse:
        return JSONResponse(status_code=201, content={"page_id": page_id, "action": "revert"})

    @app.post("/pages/{page_id}/status")
    async def status(page_id: str) -> JSONResponse:
        return JSONResponse({"page_id": page_id, "action": "status"})

    return app


async def test_unauthenticated_page_read_returns_401() -> None:
    page_id = "11111111-1111-1111-1111-111111111111"
    upstream = build_upstream_pages_app()
    app = create_app(upstream_transport=ASGITransport(app=upstream))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            f"/pages/{page_id}",
            headers={
                "X-Authenticated-Source": "spoofed",
                "X-Internal-Token": "client-secret",
            },
        )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "missing_bearer_token"


async def test_page_read_with_auth_injects_gateway_identity_headers() -> None:
    private_key, jwk = build_auth_keypair()
    token = issue_token(private_key, role="Researcher")
    page_id = "11111111-1111-1111-1111-111111111111"
    upstream = build_upstream_pages_app()
    app = create_app(upstream_transport=ASGITransport(app=upstream))
    app.state.jwks_cache._keys = [jwk]
    app.state.jwks_cache._expires_at = 10**12

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            f"/pages/{page_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "page_id": page_id,
        "source": "api-gateway",
        "role": "Researcher",
        "authorization": None,
    }


async def test_page_read_with_invalid_token_returns_401() -> None:
    page_id = "11111111-1111-1111-1111-111111111111"
    upstream = build_upstream_pages_app()
    app = create_app(upstream_transport=ASGITransport(app=upstream))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            f"/pages/{page_id}",
            headers={"Authorization": "Bearer invalid-token"},
        )

    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"
    assert response.json()["error"]["code"] == "invalid_token"


async def test_unauthenticated_page_revision_routes_return_401() -> None:
    page_id = "11111111-1111-1111-1111-111111111111"
    revision_id = "22222222-2222-2222-2222-222222222222"
    upstream = build_upstream_pages_app()
    app = create_app(upstream_transport=ASGITransport(app=upstream))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        revisions_response = await client.get(f"/pages/{page_id}/revisions")
        revision_response = await client.get(f"/pages/{page_id}/revisions/{revision_id}")

    assert revisions_response.status_code == 401
    assert revisions_response.json()["error"]["code"] == "missing_bearer_token"
    assert revision_response.status_code == 401
    assert revision_response.json()["error"]["code"] == "missing_bearer_token"


async def test_protected_page_write_requires_authentication() -> None:
    upstream = build_upstream_pages_app()
    app = create_app(upstream_transport=ASGITransport(app=upstream))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/pages", json={"slug": "bloodsucker-den"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "missing_bearer_token"


async def test_protected_page_write_injects_gateway_identity_headers() -> None:
    private_key, jwk = build_auth_keypair()
    token = issue_token(private_key, role="Editor")
    upstream = build_upstream_pages_app()
    app = create_app(upstream_transport=ASGITransport(app=upstream))
    app.state.jwks_cache._keys = [jwk]
    app.state.jwks_cache._expires_at = 10**12

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/pages",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Authenticated-User-Id": "spoofed",
                "X-Authenticated-User-Role": "Admin",
            },
            json={"slug": "bloodsucker-den"},
        )

    assert response.status_code == 201
    body = response.json()
    assert body["source"] == "api-gateway"
    assert body["user_id"] != "spoofed"
    assert body["email"] == "user@example.com"
    assert body["role"] == "Editor"
    assert body["authorization"] is None


async def test_protected_page_mutation_routes_are_forwarded() -> None:
    private_key, jwk = build_auth_keypair()
    token = issue_token(private_key, role="Researcher")
    page_id = "11111111-1111-1111-1111-111111111111"
    upstream = build_upstream_pages_app()
    app = create_app(upstream_transport=ASGITransport(app=upstream))
    app.state.jwks_cache._keys = [jwk]
    app.state.jwks_cache._expires_at = 10**12

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        draft_response = await client.post(
            f"/pages/{page_id}/drafts",
            headers={"Authorization": f"Bearer {token}"},
            json={"title": "Draft"},
        )
        metadata_response = await client.put(
            f"/pages/{page_id}/metadata",
            headers={"Authorization": f"Bearer {token}"},
            json={"tags": ["zone"]},
        )
        publish_response = await client.post(
            f"/pages/{page_id}/publish",
            headers={"Authorization": f"Bearer {token}"},
            json={"revision_id": page_id},
        )
        revert_response = await client.post(
            f"/pages/{page_id}/revert",
            headers={"Authorization": f"Bearer {token}"},
            json={"revision_id": page_id},
        )
        status_response = await client.post(
            f"/pages/{page_id}/status",
            headers={"Authorization": f"Bearer {token}"},
            json={"status": "Review"},
        )

    assert draft_response.status_code == 201
    assert draft_response.json()["source"] == "api-gateway"
    assert draft_response.json()["role"] == "Researcher"
    assert metadata_response.status_code == 200
    assert metadata_response.json() == {"page_id": page_id, "source": "api-gateway"}
    assert publish_response.status_code == 200
    assert publish_response.json() == {"page_id": page_id, "action": "publish"}
    assert revert_response.status_code == 201
    assert revert_response.json() == {"page_id": page_id, "action": "revert"}
    assert status_response.status_code == 200
    assert status_response.json() == {"page_id": page_id, "action": "status"}
