from pathlib import Path
from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from config import get_settings
from db import get_engine, reset_database_state
from main import create_app
from models import Base


async def create_test_app(tmp_path: Path, monkeypatch) -> object:
    database_path = tmp_path / "encyclopedia-metadata-test.db"
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


async def create_page(client: AsyncClient, slug: str) -> dict:
    response = await client.post(
        "/pages",
        json={
            "slug": slug,
            "type": "Article",
            "visibility": "Internal",
            "title": slug.replace("-", " ").title(),
            "summary": "Summary",
            "content": "Content",
        },
    )
    return response.json()


async def test_metadata_update_persists_tags_relationships_and_media_refs(tmp_path, monkeypatch) -> None:
    app = await create_test_app(tmp_path, monkeypatch)
    asset_id = uuid4()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        page = await create_page(client, "ecology-report")
        related_page = await create_page(client, "field-notes")
        response = await client.put(
            f"/pages/{page['page']['id']}/metadata",
            json={
                "expected_page_version": page["page"]["version"],
                "tags": [" ecology ", "rare", "rare"],
                "classifications": ["confidential", "tier-2", "tier-2"],
                "related_page_ids": [related_page["page"]["id"]],
                "media_asset_ids": [str(asset_id), str(asset_id)],
            },
        )

    body = response.json()
    assert response.status_code == 200
    assert body["page"]["tags"] == ["ecology", "rare"]
    assert body["page"]["classifications"] == ["confidential", "tier-2"]
    assert body["page"]["related_page_ids"] == [related_page["page"]["id"]]
    assert body["page"]["media_asset_ids"] == [str(asset_id)]
    assert body["page"]["version"] == page["page"]["version"] + 1


async def test_metadata_update_is_visible_in_page_state_reads(tmp_path, monkeypatch) -> None:
    app = await create_test_app(tmp_path, monkeypatch)
    asset_id = uuid4()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        page = await create_page(client, "zone-map")
        related_page = await create_page(client, "zone-addendum")
        update_response = await client.put(
            f"/pages/{page['page']['id']}/metadata",
            json={
                "expected_page_version": page["page"]["version"],
                "tags": ["navigation"],
                "classifications": ["public-release"],
                "related_page_ids": [related_page["page"]["id"]],
                "media_asset_ids": [str(asset_id)],
            },
        )
        state_response = await client.get(f"/pages/{page['page']['id']}")

    assert update_response.status_code == 200
    state_body = state_response.json()
    assert state_response.status_code == 200
    assert state_body["page"]["tags"] == ["navigation"]
    assert state_body["page"]["classifications"] == ["public-release"]
    assert state_body["page"]["related_page_ids"] == [related_page["page"]["id"]]
    assert state_body["page"]["media_asset_ids"] == [str(asset_id)]


async def test_metadata_validation_rejects_self_references(tmp_path, monkeypatch) -> None:
    app = await create_test_app(tmp_path, monkeypatch)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        page = await create_page(client, "self-linked-page")
        response = await client.put(
            f"/pages/{page['page']['id']}/metadata",
            json={
                "expected_page_version": page["page"]["version"],
                "tags": [],
                "classifications": [],
                "related_page_ids": [page["page"]["id"]],
                "media_asset_ids": [],
            },
        )

    assert response.status_code == 400
    assert "cannot reference itself" in response.json()["detail"]
