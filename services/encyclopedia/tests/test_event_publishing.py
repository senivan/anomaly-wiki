from pathlib import Path
from unittest.mock import AsyncMock
from httpx import ASGITransport, AsyncClient
import pytest

from config import get_settings
from db import get_engine, reset_database_state
from main import create_app
from models import Base
from publisher import NoopPublisher


async def create_test_app_with_mock_publisher(tmp_path: Path, monkeypatch) -> tuple:
    database_path = tmp_path / "enc-events-test.db"
    monkeypatch.setenv(
        "ENCYCLOPEDIA_SERVICE_DATABASE_URL",
        f"sqlite+aiosqlite:///{database_path}",
    )
    get_settings.cache_clear()
    reset_database_state()

    app = create_app()
    mock_publisher = AsyncMock(spec=NoopPublisher)
    app.state.publisher = mock_publisher

    async with get_engine().begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return app, mock_publisher


async def test_create_page_publishes_page_created_event(tmp_path, monkeypatch):
    app, mock_publisher = await create_test_app_with_mock_publisher(tmp_path, monkeypatch)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/pages",
            json={
                "slug": "burner",
                "type": "Anomaly",
                "visibility": "Public",
                "title": "Burner Anomaly",
                "summary": "Hot.",
                "content": "It burns.",
            },
        )

    mock_publisher.publish.assert_called_once()
    call_args = mock_publisher.publish.call_args
    assert call_args.args[0] == "page.created"
    assert "page_id" in call_args.args[1]


async def test_publish_revision_publishes_page_published_event(tmp_path, monkeypatch):
    app, mock_publisher = await create_test_app_with_mock_publisher(tmp_path, monkeypatch)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post(
            "/pages",
            json={
                "slug": "flash",
                "type": "Anomaly",
                "visibility": "Public",
                "title": "Flash",
                "summary": "Bright.",
                "content": "Flash anomaly.",
            },
        )
        page_id = create_resp.json()["page"]["id"]
        revision_id = create_resp.json()["revision"]["id"]
        page_version = create_resp.json()["page"]["version"]

        mock_publisher.reset_mock()

        await client.post(
            f"/pages/{page_id}/publish",
            json={"expected_page_version": page_version, "revision_id": revision_id},
        )

    mock_publisher.publish.assert_called_once()
    call_args = mock_publisher.publish.call_args
    assert call_args.args[0] == "page.published"
    assert call_args.args[1]["page_id"] == page_id


async def test_transition_status_publishes_status_changed_event(tmp_path, monkeypatch):
    app, mock_publisher = await create_test_app_with_mock_publisher(tmp_path, monkeypatch)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post(
            "/pages",
            json={
                "slug": "psi-storm",
                "type": "Anomaly",
                "visibility": "Internal",
                "title": "Psi Storm",
                "summary": "Mental hazard.",
                "content": "Dangerous.",
            },
        )
        page_id = create_resp.json()["page"]["id"]
        page_version = create_resp.json()["page"]["version"]

        mock_publisher.reset_mock()

        await client.post(
            f"/pages/{page_id}/status",
            json={"expected_page_version": page_version, "status": "Review"},
        )

    mock_publisher.publish.assert_called_once()
    call_args = mock_publisher.publish.call_args
    assert call_args.args[0] == "page.status_changed"
    body = call_args.args[1]
    assert body["page_id"] == page_id
    assert body["new_status"] == "Review"


async def test_create_page_succeeds_even_when_publisher_raises(tmp_path, monkeypatch):
    app, mock_publisher = await create_test_app_with_mock_publisher(tmp_path, monkeypatch)
    mock_publisher.publish.side_effect = Exception("RabbitMQ unavailable")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/pages",
            json={
                "slug": "resilient-page",
                "type": "Anomaly",
                "visibility": "Public",
                "title": "Resilient Page",
                "summary": "Should not fail.",
                "content": "Even if MQ is down.",
            },
        )

    assert response.status_code == 201


async def test_update_metadata_publishes_metadata_updated_event(tmp_path, monkeypatch):
    app, mock_publisher = await create_test_app_with_mock_publisher(tmp_path, monkeypatch)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post(
            "/pages",
            json={
                "slug": "meta-test",
                "type": "Anomaly",
                "visibility": "Public",
                "title": "Meta Test",
                "summary": "Testing metadata.",
                "content": "Content.",
            },
        )
        page_id = create_resp.json()["page"]["id"]
        page_version = create_resp.json()["page"]["version"]

        mock_publisher.reset_mock()

        await client.put(
            f"/pages/{page_id}/metadata",
            json={
                "expected_page_version": page_version,
                "tags": ["new-tag"],
                "classifications": [],
                "related_page_ids": [],
                "media_asset_ids": [],
            },
        )

    mock_publisher.publish.assert_called_once()
    call_args = mock_publisher.publish.call_args
    assert call_args.args[0] == "page.metadata_updated"
    assert call_args.args[1]["page_id"] == page_id
