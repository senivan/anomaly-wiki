from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient

from main import create_app
from tests.test_auth_validation import build_auth_keypair, issue_token


def build_upstream_pages_app() -> FastAPI:
    app = FastAPI()
    public_asset_id = "11111111-1111-1111-1111-111111111111"

    @app.get("/pages/mine")
    async def list_my_pages(request: Request) -> JSONResponse:
        return JSONResponse(
            {
                "source": request.headers.get("x-authenticated-source"),
                "user_id": request.headers.get("x-authenticated-user-id"),
                "role": request.headers.get("x-authenticated-user-role"),
                "authorization": request.headers.get("authorization"),
            }
        )

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

    @app.get("/pages/slug/{slug}")
    async def get_page_by_slug(slug: str, request: Request) -> JSONResponse:
        if slug in {"published-public", "draft-public", "published-internal"}:
            status = "Draft" if slug == "draft-public" else "Published"
            visibility = "Internal" if slug == "published-internal" else "Public"
            return JSONResponse(
                {
                    "page": {
                        "slug": slug,
                        "status": status,
                        "visibility": visibility,
                        "media_asset_ids": [public_asset_id],
                    },
                    "current_published_revision": {
                        "title": "Published public page",
                        "content": "Visible to anonymous readers.",
                    } if status == "Published" else None,
                    "current_draft_revision": None,
                }
            )
        return JSONResponse(
            {
                "slug": slug,
                "source": request.headers.get("x-authenticated-source"),
                "role": request.headers.get("x-authenticated-user-role"),
                "authorization": request.headers.get("authorization"),
            }
        )

    @app.get("/media/{asset_id}/download-url")
    async def download_url(asset_id: str, request: Request) -> JSONResponse:
        return JSONResponse(
            {
                "asset_id": asset_id,
                "url": f"http://storage.local/media/{asset_id}.svg?signature=test",
                "source": request.headers.get("x-authenticated-source"),
                "authorization": request.headers.get("authorization"),
            }
        )

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


async def test_page_read_by_slug_forwards_with_gateway_identity_headers() -> None:
    private_key, jwk = build_auth_keypair()
    token = issue_token(private_key, role="Researcher")
    upstream = build_upstream_pages_app()
    app = create_app(upstream_transport=ASGITransport(app=upstream))
    app.state.jwks_cache._keys = [jwk]
    app.state.jwks_cache._expires_at = 10**12

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/pages/slug/controller-anomaly",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "slug": "controller-anomaly",
        "source": "api-gateway",
        "role": "Researcher",
        "authorization": None,
    }


async def test_public_page_read_by_slug_allows_anonymous_published_public_page() -> None:
    upstream = build_upstream_pages_app()
    app = create_app(upstream_transport=ASGITransport(app=upstream))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/pages/slug/published-public",
            headers={
                "X-Authenticated-Source": "spoofed",
                "X-Internal-Token": "client-secret",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["page"]["slug"] == "published-public"
    assert body["page"]["status"] == "Published"
    assert body["page"]["visibility"] == "Public"


async def test_public_page_read_by_slug_hides_non_public_pages() -> None:
    upstream = build_upstream_pages_app()
    app = create_app(upstream_transport=ASGITransport(app=upstream))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        draft_response = await client.get("/pages/slug/draft-public")
        internal_response = await client.get("/pages/slug/published-internal")

    assert draft_response.status_code == 404
    assert draft_response.json()["error"]["code"] == "page_not_public"
    assert internal_response.status_code == 404
    assert internal_response.json()["error"]["code"] == "page_not_public"


async def test_public_page_media_content_redirects_only_linked_public_assets() -> None:
    asset_id = "11111111-1111-1111-1111-111111111111"
    upstream = build_upstream_pages_app()
    app = create_app(upstream_transport=ASGITransport(app=upstream))

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        follow_redirects=False,
    ) as client:
        response = await client.get(
            f"/pages/slug/published-public/media/{asset_id}/content",
            headers={
                "X-Authenticated-Source": "spoofed",
                "X-Internal-Token": "client-secret",
            },
        )

    assert response.status_code == 307
    assert response.headers["location"] == f"http://storage.local/media/{asset_id}.svg?signature=test"


async def test_public_page_media_content_hides_unlinked_or_non_public_assets() -> None:
    linked_asset_id = "11111111-1111-1111-1111-111111111111"
    unlinked_asset_id = "22222222-2222-2222-2222-222222222222"
    upstream = build_upstream_pages_app()
    app = create_app(upstream_transport=ASGITransport(app=upstream))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        unlinked_response = await client.get(
            f"/pages/slug/published-public/media/{unlinked_asset_id}/content",
        )
        draft_response = await client.get(
            f"/pages/slug/draft-public/media/{linked_asset_id}/content",
        )
        internal_response = await client.get(
            f"/pages/slug/published-internal/media/{linked_asset_id}/content",
        )

    assert unlinked_response.status_code == 404
    assert unlinked_response.json()["error"]["code"] == "media_not_public"
    assert draft_response.status_code == 404
    assert draft_response.json()["error"]["code"] == "page_not_public"
    assert internal_response.status_code == 404
    assert internal_response.json()["error"]["code"] == "page_not_public"


async def test_my_pages_forwards_with_gateway_identity_headers() -> None:
    private_key, jwk = build_auth_keypair()
    token = issue_token(private_key, role="Researcher")
    upstream = build_upstream_pages_app()
    app = create_app(upstream_transport=ASGITransport(app=upstream))
    app.state.jwks_cache._keys = [jwk]
    app.state.jwks_cache._expires_at = 10**12

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/pages/mine?status=Draft",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Authenticated-User-Id": "spoofed",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "api-gateway"
    assert body["user_id"] != "spoofed"
    assert body["role"] == "Researcher"
    assert body["authorization"] is None


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
