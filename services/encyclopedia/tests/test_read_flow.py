from pathlib import Path

from httpx import ASGITransport, AsyncClient

from config import get_settings
from db import get_engine, reset_database_state
from main import create_app
from models import Base


async def create_test_app(tmp_path: Path, monkeypatch) -> object:
    database_path = tmp_path / "encyclopedia-read-test.db"
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


async def seed_page_with_two_revisions(client: AsyncClient) -> tuple[dict, dict]:
    create_response = await client.post(
        "/pages",
        json={
            "slug": "controller-anomaly",
            "type": "Anomaly",
            "visibility": "Public",
            "title": "Controller",
            "summary": "Initial summary.",
            "content": "Initial content.",
        },
    )
    create_body = create_response.json()
    edit_response = await client.post(
        f"/pages/{create_body['page']['id']}/drafts",
        json={
            "expected_page_version": create_body["page"]["version"],
            "title": "Controller",
            "summary": "Updated summary.",
            "content": "Updated content.",
        },
    )
    return create_body, edit_response.json()


async def test_get_page_state_returns_current_draft_and_page_metadata(tmp_path, monkeypatch) -> None:
    app = await create_test_app(tmp_path, monkeypatch)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        create_body, edit_body = await seed_page_with_two_revisions(client)
        response = await client.get(f"/pages/{create_body['page']['id']}")

    body = response.json()
    assert response.status_code == 200
    assert body["page"]["id"] == create_body["page"]["id"]
    assert body["page"]["current_draft_revision_id"] == edit_body["revision"]["id"]
    assert body["current_draft_revision"]["id"] == edit_body["revision"]["id"]
    assert body["current_published_revision"] is None


async def test_list_page_revisions_returns_full_history(tmp_path, monkeypatch) -> None:
    app = await create_test_app(tmp_path, monkeypatch)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        create_body, edit_body = await seed_page_with_two_revisions(client)
        response = await client.get(f"/pages/{create_body['page']['id']}/revisions")

    body = response.json()
    assert response.status_code == 200
    assert [revision["id"] for revision in body["revisions"]] == [
        create_body["revision"]["id"],
        edit_body["revision"]["id"],
    ]


async def test_get_specific_revision_returns_lineage(tmp_path, monkeypatch) -> None:
    app = await create_test_app(tmp_path, monkeypatch)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        create_body, edit_body = await seed_page_with_two_revisions(client)
        response = await client.get(
            f"/pages/{create_body['page']['id']}/revisions/{edit_body['revision']['id']}"
        )

    body = response.json()
    assert response.status_code == 200
    assert body["revision"]["id"] == edit_body["revision"]["id"]
    assert [revision["id"] for revision in body["lineage"]] == [
        edit_body["revision"]["id"],
        create_body["revision"]["id"],
    ]
