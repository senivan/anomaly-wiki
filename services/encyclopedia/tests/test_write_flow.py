from pathlib import Path

from httpx import ASGITransport, AsyncClient

from config import get_settings
from db import get_engine, reset_database_state
from main import create_app
from models import Base


async def create_test_app(tmp_path: Path, monkeypatch) -> object:
    database_path = tmp_path / "encyclopedia-test.db"
    monkeypatch.setenv(
        "ENCYCLOPEDIA_SERVICE_DATABASE_URL",
        f"sqlite+aiosqlite:///{database_path}",
    )
    get_settings.cache_clear()
    reset_database_state()

    app = create_app()
    async with get_engine().begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return app


async def test_create_page_creates_initial_draft_revision(tmp_path, monkeypatch) -> None:
    app = await create_test_app(tmp_path, monkeypatch)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/pages",
            json={
                "slug": "burner-anomaly",
                "type": "Anomaly",
                "visibility": "Public",
                "title": "Burner",
                "summary": "Localized thermal distortion.",
                "content": "Initial draft body.",
            },
        )

    body = response.json()
    assert response.status_code == 201
    assert body["page"]["slug"] == "burner-anomaly"
    assert body["page"]["status"] == "Draft"
    assert body["page"]["current_published_revision_id"] is None
    assert body["page"]["current_draft_revision_id"] == body["revision"]["id"]
    assert body["page"]["version"] == 2
    assert body["revision"]["parent_revision_id"] is None


async def test_draft_edit_creates_new_revision_and_preserves_previous_revision(
    tmp_path,
    monkeypatch,
) -> None:
    app = await create_test_app(tmp_path, monkeypatch)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        create_response = await client.post(
            "/pages",
            json={
                "slug": "whirligig-anomaly",
                "type": "Anomaly",
                "visibility": "Public",
                "title": "Whirligig",
                "summary": "Initial summary.",
                "content": "Initial content.",
            },
        )
        create_body = create_response.json()
        edit_response = await client.post(
            f"/pages/{create_body['page']['id']}/drafts",
            json={
                "expected_page_version": create_body["page"]["version"],
                "title": "Whirligig",
                "summary": "Updated summary.",
                "content": "Updated content.",
            },
        )

    edit_body = edit_response.json()
    assert edit_response.status_code == 201
    assert edit_body["page"]["current_draft_revision_id"] == edit_body["revision"]["id"]
    assert edit_body["page"]["version"] == 3
    assert edit_body["revision"]["parent_revision_id"] == create_body["revision"]["id"]
    assert edit_body["revision"]["id"] != create_body["revision"]["id"]


async def test_stale_draft_edit_returns_conflict(tmp_path, monkeypatch) -> None:
    app = await create_test_app(tmp_path, monkeypatch)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        create_response = await client.post(
            "/pages",
            json={
                "slug": "electro-anomaly",
                "type": "Anomaly",
                "visibility": "Internal",
                "title": "Electro",
                "summary": "Initial summary.",
                "content": "Initial content.",
            },
        )
        create_body = create_response.json()

        first_edit = await client.post(
            f"/pages/{create_body['page']['id']}/drafts",
            json={
                "expected_page_version": create_body["page"]["version"],
                "title": "Electro",
                "summary": "Updated summary.",
                "content": "Updated content.",
            },
        )
        stale_edit = await client.post(
            f"/pages/{create_body['page']['id']}/drafts",
            json={
                "expected_page_version": create_body["page"]["version"],
                "title": "Electro",
                "summary": "Stale summary.",
                "content": "Stale content.",
            },
        )

    assert first_edit.status_code == 201
    assert stale_edit.status_code == 409
    assert "Expected page version" in stale_edit.json()["detail"]
