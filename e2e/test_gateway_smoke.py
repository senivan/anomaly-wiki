from __future__ import annotations

import os
from uuid import uuid4

import httpx


GATEWAY_BASE_URL = os.getenv("E2E_GATEWAY_BASE_URL", "http://localhost:8000")


async def _register_and_login(client: httpx.AsyncClient) -> str:
    email = f"e2e-{uuid4()}@example.com"
    password = "testpassword123"

    register_response = await client.post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
            "role": "Researcher",
        },
    )
    assert register_response.status_code == 201, register_response.text
    assert register_response.json()["role"] == "Researcher"

    login_response = await client.post(
        "/auth/login",
        data={"username": email, "password": password},
    )
    assert login_response.status_code == 200, login_response.text
    body = login_response.json()
    assert body["token_type"] == "bearer"
    return body["access_token"]


async def test_gateway_auth_encyclopedia_media_and_search_smoke() -> None:
    async with httpx.AsyncClient(
        base_url=GATEWAY_BASE_URL,
        timeout=30.0,
    ) as client:
        ready_response = await client.get("/ready")
        assert ready_response.status_code == 200, ready_response.text

        token = await _register_and_login(client)
        auth_headers = {"Authorization": f"Bearer {token}"}

        slug = f"e2e-burner-{uuid4().hex[:8]}"
        create_response = await client.post(
            "/pages",
            headers=auth_headers,
            json={
                "slug": slug,
                "type": "Anomaly",
                "visibility": "Public",
                "title": "E2E Burner Anomaly",
                "summary": "A deterministic page created by the CI smoke test.",
                "content": "Initial field notes for the end-to-end smoke test.",
            },
        )
        assert create_response.status_code == 201, create_response.text
        created = create_response.json()
        page_id = created["page"]["id"]
        page_version = created["page"]["version"]

        read_response = await client.get(f"/pages/{page_id}", headers=auth_headers)
        assert read_response.status_code == 200, read_response.text
        assert read_response.json()["page"]["slug"] == slug

        draft_response = await client.post(
            f"/pages/{page_id}/drafts",
            headers=auth_headers,
            json={
                "expected_page_version": page_version,
                "title": "E2E Burner Anomaly Updated",
                "summary": "Updated summary from the CI smoke test.",
                "content": "Updated smoke-test content before publication.",
            },
        )
        assert draft_response.status_code == 201, draft_response.text
        draft = draft_response.json()

        publish_response = await client.post(
            f"/pages/{page_id}/publish",
            headers=auth_headers,
            json={
                "expected_page_version": draft["page"]["version"],
                "revision_id": draft["revision"]["id"],
            },
        )
        assert publish_response.status_code == 200, publish_response.text
        published = publish_response.json()
        assert published["page"]["status"] == "Published"
        assert published["current_published_revision"]["title"] == "E2E Burner Anomaly Updated"

        metadata_response = await client.put(
            f"/pages/{page_id}/metadata",
            headers=auth_headers,
            json={
                "expected_page_version": published["page"]["version"],
                "tags": ["e2e", "burner"],
                "classifications": ["ci-smoke"],
                "related_page_ids": [],
                "media_asset_ids": [],
            },
        )
        assert metadata_response.status_code == 200, metadata_response.text
        assert metadata_response.json()["page"]["tags"] == ["e2e", "burner"]

        upload_response = await client.post(
            "/media",
            headers=auth_headers,
            files={"file": ("e2e-note.txt", b"zone smoke test artifact", "text/plain")},
        )
        assert upload_response.status_code == 201, upload_response.text
        asset_id = upload_response.json()["id"]

        media_response = await client.get(f"/media/{asset_id}", headers=auth_headers)
        assert media_response.status_code == 200, media_response.text
        assert media_response.json()["filename"] == "e2e-note.txt"

        download_response = await client.get(
            f"/media/{asset_id}/download-url",
            headers=auth_headers,
        )
        assert download_response.status_code == 200, download_response.text
        download_body = download_response.json()
        assert download_body["asset_id"] == asset_id
        assert download_body["url"]

        search_response = await client.get("/search", params={"q": "burner"})
        assert search_response.status_code == 200, search_response.text
        search_body = search_response.json()
        assert "total" in search_body
        assert "hits" in search_body
