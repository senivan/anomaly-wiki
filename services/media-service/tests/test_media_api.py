from uuid import UUID, uuid4

from httpx import ASGITransport, AsyncClient

from config import get_settings
from db import reset_database_state
from main import create_app


class FakeObjectStorage:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}
        self.available = True

    async def put_object(
        self,
        *,
        storage_path: str,
        data: bytes,
        content_type: str,
    ) -> None:
        self.objects[storage_path] = (data, content_type)

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
                headers={"X-Authenticated-User-Id": str(uploaded_by)},
                files={"file": ("photo.jpg", b"zone photo", "image/jpeg")},
            )

    assert response.status_code == 201
    body = response.json()
    asset_id = UUID(body["id"])
    assert body["filename"] == "photo.jpg"
    assert body["mime_type"] == "image/jpeg"
    assert body["size_bytes"] == len(b"zone photo")
    assert body["uploaded_by"] == str(uploaded_by)
    assert body["checksum_sha256"] == "f11ee40d5aca71c20a8c6d9d1ef30188617e243e798bc8af836980b360d64388"
    assert body["storage_path"] == f"assets/{asset_id}/photo.jpg"
    assert storage.objects[body["storage_path"]] == (b"zone photo", "image/jpeg")
    reset_caches()


async def test_upload_requires_authenticated_user_header(monkeypatch) -> None:
    app = await build_test_app(monkeypatch)

    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/media",
                files={"file": ("photo.jpg", b"zone photo", "image/jpeg")},
            )

    assert response.status_code == 401
    reset_caches()


async def test_metadata_lookup_and_signed_url(monkeypatch) -> None:
    storage = FakeObjectStorage()
    app = await build_test_app(monkeypatch, storage)
    uploaded_by = uuid4()

    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            upload_response = await client.post(
                "/media",
                headers={"X-Authenticated-User-Id": str(uploaded_by)},
                files={"file": ("map.pdf", b"map-data", "application/pdf")},
            )
            asset_id = upload_response.json()["id"]

            metadata_response = await client.get(f"/media/{asset_id}")
            url_response = await client.get(f"/media/{asset_id}/download-url")

    assert metadata_response.status_code == 200
    assert metadata_response.json()["id"] == asset_id
    assert url_response.status_code == 200
    assert url_response.json() == {
        "asset_id": asset_id,
        "url": f"http://object-storage.test/assets/{asset_id}/map.pdf?expires=120",
        "expires_in_seconds": 120,
    }
    reset_caches()


async def test_missing_asset_returns_404(monkeypatch) -> None:
    app = await build_test_app(monkeypatch)
    missing_asset_id = uuid4()

    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/media/{missing_asset_id}")

    assert response.status_code == 404
    reset_caches()
