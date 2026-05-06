from __future__ import annotations

from uuid import uuid4

import httpx

from helpers import wait_for_search_absence, wait_for_search_hit


async def _create_page(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    *,
    slug_prefix: str,
    title: str,
    visibility: str = "Public",
    type_: str = "Anomaly",
    summary: str = "Whole-system E2E summary.",
    content: str = "Whole-system E2E content.",
) -> dict:
    slug = f"{slug_prefix}-{uuid4().hex[:8]}"
    response = await client.post(
        "/pages",
        headers=auth_headers,
        json={
            "slug": slug,
            "type": type_,
            "visibility": visibility,
            "title": title,
            "summary": summary,
            "content": content,
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    body["e2e_slug"] = slug
    return body


async def _publish_revision(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    page_state: dict,
) -> dict:
    response = await client.post(
        f"/pages/{page_state['page']['id']}/publish",
        headers=auth_headers,
        json={
            "expected_page_version": page_state["page"]["version"],
            "revision_id": page_state["revision"]["id"],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_public_publish_journey_indexes_page_for_anonymous_search(
    gateway_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    title = f"E2E System Public Journey {uuid4().hex[:8]}"
    created = await _create_page(
        gateway_client,
        auth_headers,
        slug_prefix="e2e-system-public",
        title=title,
        summary="Published public journey should become searchable.",
        content="Published public journey content for real indexer coverage.",
    )

    published = await _publish_revision(gateway_client, auth_headers, created)
    assert published["page"]["status"] == "Published"

    hit = await wait_for_search_hit(
        gateway_client,
        slug=created["e2e_slug"],
        q=title,
    )
    assert hit["title"] == title
    assert hit["visibility"] == "Public"
    assert hit["status"] == "Published"


async def test_internal_draft_journey_is_indexed_but_not_publicly_visible(
    gateway_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    title = f"E2E System Internal Draft {uuid4().hex[:8]}"
    created = await _create_page(
        gateway_client,
        auth_headers,
        slug_prefix="e2e-system-internal",
        title=title,
        visibility="Internal",
        type_="Researcher Note",
        summary="Internal draft journey should require authenticated search.",
        content="Internal draft journey content for real indexer coverage.",
    )

    hit = await wait_for_search_hit(
        gateway_client,
        slug=created["e2e_slug"],
        q=title,
        headers=auth_headers,
        params={"visibility": "Internal", "status": "Draft"},
    )
    assert hit["visibility"] == "Internal"
    assert hit["status"] == "Draft"

    anonymous_response = await gateway_client.get("/search", params={"q": title})
    assert anonymous_response.status_code == 200, anonymous_response.text
    assert all(hit["slug"] != created["e2e_slug"] for hit in anonymous_response.json()["hits"])


async def test_metadata_update_journey_propagates_tags_to_search(
    gateway_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    suffix = uuid4().hex[:8]
    title = f"E2E System Metadata Journey {suffix}"
    tag = f"system-metadata-{suffix}"
    created = await _create_page(
        gateway_client,
        auth_headers,
        slug_prefix="e2e-system-metadata",
        title=title,
        summary="Metadata update journey should refresh indexed tags.",
        content="Metadata update journey content for real indexer coverage.",
    )
    published = await _publish_revision(gateway_client, auth_headers, created)

    metadata_response = await gateway_client.put(
        f"/pages/{published['page']['id']}/metadata",
        headers=auth_headers,
        json={
            "expected_page_version": published["page"]["version"],
            "tags": [tag],
            "classifications": ["system-journey"],
            "related_page_ids": [],
            "media_asset_ids": [],
        },
    )
    assert metadata_response.status_code == 200, metadata_response.text

    await wait_for_search_hit(
        gateway_client,
        slug=created["e2e_slug"],
        q=title,
        params={"tags": tag},
    )


async def test_archived_page_journey_removes_page_from_search(
    gateway_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    title = f"E2E System Archive Journey {uuid4().hex[:8]}"
    created = await _create_page(
        gateway_client,
        auth_headers,
        slug_prefix="e2e-system-archive",
        title=title,
        summary="Archived journey should disappear from search.",
        content="Archived journey content for real indexer coverage.",
    )
    published = await _publish_revision(gateway_client, auth_headers, created)

    await wait_for_search_hit(
        gateway_client,
        slug=created["e2e_slug"],
        q=title,
    )

    archive_response = await gateway_client.post(
        f"/pages/{published['page']['id']}/status",
        headers=auth_headers,
        json={
            "expected_page_version": published["page"]["version"],
            "status": "Archived",
        },
    )
    assert archive_response.status_code == 200, archive_response.text

    await wait_for_search_absence(
        gateway_client,
        slug=created["e2e_slug"],
        q=title,
    )


async def test_media_linked_page_journey_preserves_media_and_search_visibility(
    gateway_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    suffix = uuid4().hex[:8]
    title = f"E2E System Media Journey {suffix}"
    tag = f"system-media-{suffix}"

    upload_response = await gateway_client.post(
        "/media",
        headers=auth_headers,
        files={"file": ("system-journey.txt", b"linked system media", "text/plain")},
    )
    assert upload_response.status_code == 201, upload_response.text
    asset = upload_response.json()

    created = await _create_page(
        gateway_client,
        auth_headers,
        slug_prefix="e2e-system-media",
        title=title,
        summary="Media-linked page journey should preserve metadata and search.",
        content="Media-linked page journey content for real indexer coverage.",
    )
    published = await _publish_revision(gateway_client, auth_headers, created)

    metadata_response = await gateway_client.put(
        f"/pages/{published['page']['id']}/metadata",
        headers=auth_headers,
        json={
            "expected_page_version": published["page"]["version"],
            "tags": [tag],
            "classifications": ["system-journey"],
            "related_page_ids": [],
            "media_asset_ids": [asset["id"]],
        },
    )
    assert metadata_response.status_code == 200, metadata_response.text

    page_response = await gateway_client.get(
        f"/pages/{published['page']['id']}",
        headers=auth_headers,
    )
    assert page_response.status_code == 200, page_response.text
    page = page_response.json()["page"]
    assert asset["id"] in page["media_asset_ids"]

    download_response = await gateway_client.get(
        f"/media/{asset['id']}/download-url",
        headers=auth_headers,
    )
    assert download_response.status_code == 200, download_response.text
    object_response = await gateway_client.get(download_response.json()["url"])
    assert object_response.status_code == 200, object_response.text
    assert object_response.content == b"linked system media"

    hit = await wait_for_search_hit(
        gateway_client,
        slug=created["e2e_slug"],
        q=title,
        params={"tags": tag},
    )
    assert hit["slug"] == created["e2e_slug"]
