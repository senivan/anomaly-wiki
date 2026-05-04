from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient

from main import create_app
from tests.test_auth_validation import build_auth_keypair, issue_token


async def test_media_upload_is_forwarded_with_gateway_identity_headers() -> None:
    private_key, jwk = build_auth_keypair()
    token = issue_token(private_key, role="Researcher")

    upstream_app = FastAPI()

    @upstream_app.post("/media")
    async def upload(request: Request) -> JSONResponse:
        form = await request.form()
        file = form["file"]
        return JSONResponse(
            status_code=201,
            content={
                "filename": file.filename,
                "content_type": file.content_type,
                "user_id": request.headers.get("x-authenticated-user-id"),
                "email": request.headers.get("x-authenticated-user-email"),
                "role": request.headers.get("x-authenticated-user-role"),
                "source": request.headers.get("x-authenticated-source"),
                "authorization": request.headers.get("authorization"),
            },
        )

    app = create_app(upstream_transport=ASGITransport(app=upstream_app))
    app.state.jwks_cache._keys = [jwk]
    app.state.jwks_cache._expires_at = 10**12

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/media",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Authenticated-User-Id": "spoofed",
                "X-Authenticated-User-Role": "Admin",
            },
            files={"file": ("photo.jpg", b"zone photo", "image/jpeg")},
        )

    assert response.status_code == 201
    body = response.json()
    assert body["filename"] == "photo.jpg"
    assert body["content_type"] == "image/jpeg"
    assert body["user_id"] != "spoofed"
    assert body["email"] == "user@example.com"
    assert body["role"] == "Researcher"
    assert body["source"] == "api-gateway"
    assert body["authorization"] is None


async def test_media_metadata_and_download_url_are_forwarded() -> None:
    private_key, jwk = build_auth_keypair()
    token = issue_token(private_key, role="Editor")
    asset_id = "11111111-1111-1111-1111-111111111111"

    upstream_app = FastAPI()

    @upstream_app.get("/media/{asset_id}")
    async def metadata(asset_id: str, request: Request) -> JSONResponse:
        return JSONResponse(
            {
                "asset_id": asset_id,
                "role": request.headers.get("x-authenticated-user-role"),
            }
        )

    @upstream_app.get("/media/{asset_id}/download-url")
    async def download_url(asset_id: str, request: Request) -> JSONResponse:
        return JSONResponse(
            {
                "asset_id": asset_id,
                "source": request.headers.get("x-authenticated-source"),
            }
        )

    app = create_app(upstream_transport=ASGITransport(app=upstream_app))
    app.state.jwks_cache._keys = [jwk]
    app.state.jwks_cache._expires_at = 10**12

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        metadata_response = await client.get(
            f"/media/{asset_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        url_response = await client.get(
            f"/media/{asset_id}/download-url",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert metadata_response.status_code == 200
    assert metadata_response.json() == {"asset_id": asset_id, "role": "Editor"}
    assert url_response.status_code == 200
    assert url_response.json() == {"asset_id": asset_id, "source": "api-gateway"}
