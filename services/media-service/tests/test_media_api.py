from uuid import UUID, uuid4

from httpx import ASGITransport, AsyncClient

from config import get_settings
from db import reset_database_state
from main import create_app

GATEWAY_HEADERS = {"X-Authenticated-Source": "api-gateway"}


class FakeObjectStorage:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}
        self.deleted: list[str] = []
        self.available = True

    async def put_object(
        self,
        *,
        storage_path: str,
        data: bytes,
        content_type: str,
    ) -> None:
        self.objects[storage_path] = (data, content_type)

    async def delete_object(self, *, storage_path: str) -> None:
        self.objects.pop(storage_path, None)
        self.deleted.append(storage_path)

    async def presigned_get_url(
        self,
        *,
        storage_path: str,
        expires_in_seconds: int,
    ) -> str:
        return f"http://object-storage.test/{storage_path}?expires={expires_in_seconds}"

    async def check_connection(self) -> None:
        if not self.available:
            raise RuntimeError("object storage unavailable")


def reset_caches() -> None:
    get_settings.cache_clear()
    reset_database_state()


async def build_test_app(monkeypatch, storage: FakeObjectStorage | None = None):
    monkeypatch.setenv("MEDIA_SERVICE_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("MEDIA_SERVICE_SIGNED_URL_TTL_SECONDS", "120")
    reset_caches()
    app = create_app(storage_backend=storage or FakeObjectStorage())
    return app


async def test_healthcheck(monkeypatch) -> None:
    app = await build_test_app(monkeypatch)
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    reset_caches()


async def test_readiness_checks_database_and_object_storage(monkeypatch) -> None:
    storage = FakeObjectStorage()
    app = await build_test_app(monkeypatch, storage)

    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "services": {
            "database": {"status": "ok"},
            "object_storage": {"status": "ok"},
        },
    }
    reset_caches()


async def test_upload_creates_metadata_and_object(monkeypatch) -> None:
    storage = FakeObjectStorage()
    app = await build_test_app(monkeypatch, storage)
    uploaded_by = uuid4()

    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/media",
                headers={**GATEWAY_HEADERS, "X-Authenticated-User-Id": str(uploaded_by)},
                files={"file": ("photo.jpg", b"zone photo", "image/jpeg")},
            )

    assert response.status_code == 201
    body = response.json()
    asset_id = UUID(body["id"])
    assert body["filename"] == "photo.jpg"
    assert body["mime_type"] == "image/jpeg"
    assert body["content_type"] == "image/jpeg"
    assert body["size_bytes"] == len(b"zone photo")
    assert body["uploaded_by"] == str(uploaded_by)
    assert body["checksum_sha256"] == "f11ee40d5aca71c20a8c6d9d1ef30188617e243e798bc8af836980b360d64388"
    assert body["storage_path"] == f"assets/{asset_id}/photo.jpg"
    assert storage.objects[body["storage_path"]] == (b"zone photo", "image/jpeg")
    reset_caches()


async def test_upload_requires_gateway_source_header(monkeypatch) -> None:
    """Requests without X-Authenticated-Source: api-gateway must be rejected."""
    app = await build_test_app(monkeypatch)
    uploaded_by = uuid4()

    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/media",
                headers={"X-Authenticated-User-Id": str(uploaded_by)},
                files={"file": ("photo.jpg", b"zone photo", "image/jpeg")},
            )

    assert response.status_code == 403
    reset_caches()


async def test_upload_requires_authenticated_user_header(monkeypatch) -> None:
    app = await build_test_app(monkeypatch)

    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/media",
                headers=GATEWAY_HEADERS,
                files={"file": ("photo.jpg", b"zone photo", "image/jpeg")},
            )

    assert response.status_code == 401
    reset_caches()


async def test_upload_rejects_oversized_file(monkeypatch) -> None:
    monkeypatch.setenv("MEDIA_SERVICE_MAX_UPLOAD_BYTES", "10")
    app = await build_test_app(monkeypatch)
    uploaded_by = uuid4()

    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/media",
                headers={**GATEWAY_HEADERS, "X-Authenticated-User-Id": str(uploaded_by)},
                files={"file": ("big.bin", b"x" * 11, "application/octet-stream")},
            )

    assert response.status_code == 413
    reset_caches()


async def test_upload_rejects_overlong_filename(monkeypatch) -> None:
    app = await build_test_app(monkeypatch)
    uploaded_by = uuid4()
    long_name = "a" * 256 + ".jpg"

    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/media",
                headers={**GATEWAY_HEADERS, "X-Authenticated-User-Id": str(uploaded_by)},
                files={"file": (long_name, b"data", "image/jpeg")},
            )

    assert response.status_code == 400
    reset_caches()


async def test_upload_cleans_up_object_on_db_failure(monkeypatch) -> None:
    """If the DB commit fails after a successful put_object, the blob is deleted."""
    from unittest.mock import AsyncMock, patch

    storage = FakeObjectStorage()
    app = await build_test_app(monkeypatch, storage)
    uploaded_by = uuid4()

    async with app.router.lifespan_context(app):
        # raise_app_exceptions=False so we can inspect the 500 response and
        # storage state rather than having the RuntimeError propagate into the test.
        async with AsyncClient(
            transport=ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://test",
        ) as client:
            with patch(
                "routes.media.MediaAssetRepository.create_asset",
                new_callable=AsyncMock,
                side_effect=RuntimeError("db boom"),
            ):
                response = await client.post(
                    "/media",
                    headers={**GATEWAY_HEADERS, "X-Authenticated-User-Id": str(uploaded_by)},
                    files={"file": ("photo.jpg", b"zone photo", "image/jpeg")},
                )

    assert response.status_code == 500
    # The uploaded object must have been removed from storage.
    assert len(storage.objects) == 0
    assert len(storage.deleted) == 1
    reset_caches()


async def test_metadata_lookup_requires_gateway_source(monkeypatch) -> None:
    storage = FakeObjectStorage()
    app = await build_test_app(monkeypatch, storage)
    uploaded_by = uuid4()

    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            upload_response = await client.post(
                "/media",
                headers={**GATEWAY_HEADERS, "X-Authenticated-User-Id": str(uploaded_by)},
                files={"file": ("map.pdf", b"map-data", "application/pdf")},
            )
            asset_id = upload_response.json()["id"]

            # No source header → 403
            metadata_response = await client.get(f"/media/{asset_id}")
            url_response = await client.get(f"/media/{asset_id}/download-url")

    assert metadata_response.status_code == 403
    assert url_response.status_code == 403
    reset_caches()


async def test_metadata_lookup_and_signed_url(monkeypatch) -> None:
    storage = FakeObjectStorage()
    app = await build_test_app(monkeypatch, storage)
    uploaded_by = uuid4()

    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            upload_response = await client.post(
                "/media",
                headers={**GATEWAY_HEADERS, "X-Authenticated-User-Id": str(uploaded_by)},
                files={"file": ("map.pdf", b"map-data", "application/pdf")},
            )
            asset_id = upload_response.json()["id"]

            metadata_response = await client.get(f"/media/{asset_id}", headers=GATEWAY_HEADERS)
            url_response = await client.get(
                f"/media/{asset_id}/download-url", headers=GATEWAY_HEADERS
            )

    assert metadata_response.status_code == 200
    assert metadata_response.json()["id"] == asset_id
    assert url_response.status_code == 200
    assert url_response.json() == {
        "asset_id": asset_id,
        "url": f"http://object-storage.test/assets/{asset_id}/map.pdf?expires=120",
        "expires_in_seconds": 120,
    }
    reset_caches()


async def test_download_url_rewrites_internal_hostname(monkeypatch) -> None:
    monkeypatch.setenv("MEDIA_SERVICE_PUBLIC_STORAGE_BASE_URL", "http://localhost:9000")
    storage = FakeObjectStorage()
    app = await build_test_app(monkeypatch, storage)
    uploaded_by = uuid4()

    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            upload_response = await client.post(
                "/media",
                headers={**GATEWAY_HEADERS, "X-Authenticated-User-Id": str(uploaded_by)},
                files={"file": ("file.bin", b"data", "application/octet-stream")},
            )
            asset_id = upload_response.json()["id"]

            url_response = await client.get(
                f"/media/{asset_id}/download-url", headers=GATEWAY_HEADERS
            )

    # object-storage.test should be replaced with localhost:9000
    assert url_response.status_code == 200
    download_url = url_response.json()["url"]
    assert download_url.startswith("http://localhost:9000/")
    reset_caches()


async def test_missing_asset_returns_404(monkeypatch) -> None:
    app = await build_test_app(monkeypatch)
    missing_asset_id = uuid4()

    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/media/{missing_asset_id}", headers=GATEWAY_HEADERS)

    assert response.status_code == 404
    reset_caches()
