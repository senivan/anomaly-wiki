from __future__ import annotations

from uuid import uuid4

import httpx


async def test_full_page_lifecycle_and_revision_reads(
    gateway_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    slug = f"e2e-lifecycle-{uuid4().hex[:8]}"
    create_response = await gateway_client.post(
        "/pages",
        headers=auth_headers,
        json={
            "slug": slug,
            "type": "Incident",
            "visibility": "Internal",
            "title": "E2E Lifecycle Incident",
            "summary": "Initial lifecycle summary.",
            "content": "Initial lifecycle content.",
        },
    )
    assert create_response.status_code == 201, create_response.text
    created = create_response.json()
    page_id = created["page"]["id"]
    first_revision_id = created["revision"]["id"]

    draft_response = await gateway_client.post(
        f"/pages/{page_id}/drafts",
        headers=auth_headers,
        json={
            "expected_page_version": created["page"]["version"],
            "title": "E2E Lifecycle Incident Draft",
            "summary": "Draft lifecycle summary.",
            "content": "Draft lifecycle content.",
            "parent_revision_id": first_revision_id,
        },
    )
    assert draft_response.status_code == 201, draft_response.text
    draft = draft_response.json()

    publish_response = await gateway_client.post(
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

    revisions_response = await gateway_client.get(
        f"/pages/{page_id}/revisions",
        headers=auth_headers,
    )
    assert revisions_response.status_code == 200, revisions_response.text
    revisions = revisions_response.json()["revisions"]
    assert [revision["id"] for revision in revisions] == [first_revision_id, draft["revision"]["id"]]

    revision_response = await gateway_client.get(
        f"/pages/{page_id}/revisions/{draft['revision']['id']}",
        headers=auth_headers,
    )
    assert revision_response.status_code == 200, revision_response.text
    revision_body = revision_response.json()
    assert revision_body["revision"]["title"] == "E2E Lifecycle Incident Draft"
    assert revision_body["lineage"][0]["id"] == first_revision_id

    revert_response = await gateway_client.post(
        f"/pages/{page_id}/revert",
        headers=auth_headers,
        json={
            "expected_page_version": published["page"]["version"],
            "revision_id": first_revision_id,
        },
    )
    assert revert_response.status_code == 201, revert_response.text
    reverted = revert_response.json()
    assert reverted["revision"]["title"] == "E2E Lifecycle Incident"

    review_response = await gateway_client.post(
        f"/pages/{page_id}/status",
        headers=auth_headers,
        json={
            "expected_page_version": reverted["page"]["version"],
            "status": "Review",
        },
    )
    assert review_response.status_code == 200, review_response.text
    assert review_response.json()["page"]["status"] == "Review"

    invalid_response = await gateway_client.post(
        f"/pages/{page_id}/status",
        headers=auth_headers,
        json={
            "expected_page_version": review_response.json()["page"]["version"],
            "status": "Published",
        },
    )
    assert invalid_response.status_code == 400, invalid_response.text


async def test_stale_page_versions_conflict_through_gateway(
    gateway_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    slug = f"e2e-conflict-{uuid4().hex[:8]}"
    create_response = await gateway_client.post(
        "/pages",
        headers=auth_headers,
        json={
            "slug": slug,
            "type": "Article",
            "visibility": "Public",
            "title": "E2E Conflict Page",
            "content": "Version conflict content.",
        },
    )
    assert create_response.status_code == 201, create_response.text
    created = create_response.json()
    page_id = created["page"]["id"]
    stale_version = created["page"]["version"]

    first_update = await gateway_client.put(
        f"/pages/{page_id}/metadata",
        headers=auth_headers,
        json={
            "expected_page_version": stale_version,
            "tags": ["first"],
            "classifications": [],
            "related_page_ids": [],
            "media_asset_ids": [],
        },
    )
    assert first_update.status_code == 200, first_update.text

    stale_update = await gateway_client.put(
        f"/pages/{page_id}/metadata",
        headers=auth_headers,
        json={
            "expected_page_version": stale_version,
            "tags": ["second"],
            "classifications": [],
            "related_page_ids": [],
            "media_asset_ids": [],
        },
    )
    assert stale_update.status_code == 409, stale_update.text

    stale_draft = await gateway_client.post(
        f"/pages/{page_id}/drafts",
        headers=auth_headers,
        json={
            "expected_page_version": stale_version,
            "title": "Stale Draft",
            "content": "This draft should conflict.",
        },
    )
    assert stale_draft.status_code == 409, stale_draft.text
