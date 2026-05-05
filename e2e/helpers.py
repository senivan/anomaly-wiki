from __future__ import annotations

from uuid import uuid4

import httpx


async def register_and_login(
    client: httpx.AsyncClient,
    *,
    requested_role: str = "Researcher",
) -> tuple[str, dict]:
    email = f"e2e-{uuid4()}@example.com"
    password = "testpassword123"

    register_response = await client.post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
            "role": requested_role,
        },
    )
    assert register_response.status_code == 201, register_response.text
    user = register_response.json()

    login_response = await client.post(
        "/auth/login",
        data={"username": email, "password": password},
    )
    assert login_response.status_code == 200, login_response.text
    body = login_response.json()
    assert body["token_type"] == "bearer"
    return body["access_token"], user


async def create_published_page(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    *,
    slug_prefix: str = "e2e-page",
) -> dict:
    slug = f"{slug_prefix}-{uuid4().hex[:8]}"
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

    draft_response = await client.post(
        f"/pages/{page_id}/drafts",
        headers=auth_headers,
        json={
            "expected_page_version": created["page"]["version"],
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
    published["e2e_slug"] = slug
    return published
