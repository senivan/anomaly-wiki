from pathlib import Path

from httpx import ASGITransport, AsyncClient

from config import get_settings
from db import get_engine, reset_database_state
from main import create_app
from models import Base


async def create_test_app(tmp_path: Path, monkeypatch) -> object:
    database_path = tmp_path / "encyclopedia-lifecycle-test.db"
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
            "slug": "bloodsucker-dossier",
            "type": "Article",
            "visibility": "Internal",
            "title": "Bloodsucker Dossier",
            "summary": "First draft.",
            "content": "Initial content.",
        },
    )
    create_body = create_response.json()
    edit_response = await client.post(
        f"/pages/{create_body['page']['id']}/drafts",
        json={
            "expected_page_version": create_body["page"]["version"],
            "title": "Bloodsucker Dossier",
            "summary": "Second draft.",
            "content": "Updated content.",
        },
    )
    return create_body, edit_response.json()


async def test_publish_preserves_draft_history_and_sets_published_pointer(tmp_path, monkeypatch) -> None:
    app = await create_test_app(tmp_path, monkeypatch)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        create_body, edit_body = await seed_page_with_two_revisions(client)
        response = await client.post(
            f"/pages/{create_body['page']['id']}/publish",
            json={
                "expected_page_version": edit_body["page"]["version"],
                "revision_id": create_body["revision"]["id"],
            },
        )

    body = response.json()
    assert response.status_code == 200
    assert body["page"]["status"] == "Published"
    assert body["page"]["current_published_revision_id"] == create_body["revision"]["id"]
    assert body["page"]["current_draft_revision_id"] == edit_body["revision"]["id"]
    assert body["current_published_revision"]["id"] == create_body["revision"]["id"]
    assert body["current_draft_revision"]["id"] == edit_body["revision"]["id"]


async def test_revert_creates_new_revision_derived_from_old_revision(tmp_path, monkeypatch) -> None:
    app = await create_test_app(tmp_path, monkeypatch)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        create_body, edit_body = await seed_page_with_two_revisions(client)
        publish_response = await client.post(
            f"/pages/{create_body['page']['id']}/publish",
            json={
                "expected_page_version": edit_body["page"]["version"],
                "revision_id": create_body["revision"]["id"],
            },
        )
        publish_body = publish_response.json()
        revert_response = await client.post(
            f"/pages/{create_body['page']['id']}/revert",
            json={
                "expected_page_version": publish_body["page"]["version"],
                "revision_id": create_body["revision"]["id"],
            },
        )

    body = revert_response.json()
    assert revert_response.status_code == 201
    assert body["page"]["status"] == "Draft"
    assert body["page"]["current_draft_revision_id"] == body["revision"]["id"]
    assert body["revision"]["parent_revision_id"] == create_body["revision"]["id"]
    assert body["revision"]["content"] == create_body["revision"]["content"]


async def test_status_transitions_are_explicit_and_reject_invalid_moves(tmp_path, monkeypatch) -> None:
    app = await create_test_app(tmp_path, monkeypatch)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        create_response = await client.post(
            "/pages",
            json={
                "slug": "controller-report",
                "type": "Incident",
                "visibility": "Internal",
                "title": "Controller Report",
                "summary": "Initial draft.",
                "content": "Initial content.",
            },
        )
        create_body = create_response.json()
        review_response = await client.post(
            f"/pages/{create_body['page']['id']}/status",
            json={
                "expected_page_version": create_body["page"]["version"],
                "status": "Review",
            },
        )
        invalid_response = await client.post(
            f"/pages/{create_body['page']['id']}/status",
            json={
                "expected_page_version": review_response.json()["page"]["version"],
                "status": "Published",
            },
        )

    assert review_response.status_code == 200
    assert review_response.json()["page"]["status"] == "Review"
    assert invalid_response.status_code == 400
    assert "not allowed" in invalid_response.json()["detail"]
