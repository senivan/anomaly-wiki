from __future__ import annotations

from uuid import uuid4

import httpx

OPENSEARCH_BASE_URL = "http://localhost:9200"
OPENSEARCH_INDEX = "anomaly-wiki-pages"


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


async def seed_search_document(
    document: dict,
    *,
    doc_id: str | None = None,
) -> str:
    doc_id = doc_id or document["page_id"]
    async with httpx.AsyncClient(base_url=OPENSEARCH_BASE_URL, timeout=20.0) as client:
        response = await client.put(f"/{OPENSEARCH_INDEX}/_doc/{doc_id}", json=document)
        assert response.status_code in {200, 201}, response.text
        refresh_response = await client.post(f"/{OPENSEARCH_INDEX}/_refresh")
        assert refresh_response.status_code == 200, refresh_response.text
    return doc_id


def search_document(
    *,
    page_id: str | None = None,
    slug: str | None = None,
    title: str = "E2E Seeded Burner",
    status: str = "Published",
    visibility: str = "Public",
    tags: list[str] | None = None,
    type_: str = "Anomaly",
    aliases: list[str] | None = None,
) -> dict:
    page_id = page_id or str(uuid4())
    slug = slug or f"e2e-search-{uuid4().hex[:8]}"
    return {
        "page_id": page_id,
        "slug": slug,
        "type": type_,
        "status": status,
        "visibility": visibility,
        "tags": tags or ["e2e"],
        "title": title,
        "summary": f"Search fixture for {title}",
        "content_text": f"{title} searchable content for the full E2E suite.",
        "aliases": aliases or [],
    }
