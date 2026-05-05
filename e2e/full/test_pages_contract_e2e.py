from __future__ import annotations

from uuid import uuid4

import httpx

from helpers import create_published_page


async def test_page_slug_uniqueness_and_missing_page_contract(
    gateway_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    slug = f"e2e-unique-{uuid4().hex[:8]}"

    first_response = await gateway_client.post(
        "/pages",
        headers=auth_headers,
        json={
            "slug": slug,
            "type": "Anomaly",
            "visibility": "Public",
            "title": "Unique Page",
            "content": "First page with unique slug.",
        },
    )
    assert first_response.status_code == 201, first_response.text

    duplicate_response = await gateway_client.post(
        "/pages",
        headers=auth_headers,
        json={
            "slug": slug,
            "type": "Anomaly",
            "visibility": "Public",
            "title": "Duplicate Page",
            "content": "This slug should not be accepted twice.",
        },
    )
    assert duplicate_response.status_code in {400, 409}, duplicate_response.text

    missing_response = await gateway_client.get(
        f"/pages/{uuid4()}",
        headers=auth_headers,
    )
    assert missing_response.status_code == 404, missing_response.text


async def test_metadata_can_link_pages_and_media_assets(
    gateway_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    source = await create_published_page(
        gateway_client,
        auth_headers,
        slug_prefix="e2e-source",
    )
    target = await create_published_page(
        gateway_client,
        auth_headers,
        slug_prefix="e2e-target",
    )

    source_page_id = source["page"]["id"]
    target_page_id = target["page"]["id"]

    upload_response = await gateway_client.post(
        "/media",
        headers=auth_headers,
        files={"file": ("metadata-link.txt", b"linked media", "text/plain")},
    )
    assert upload_response.status_code == 201, upload_response.text
    asset_id = upload_response.json()["id"]

    metadata_response = await gateway_client.put(
        f"/pages/{source_page_id}/metadata",
        headers=auth_headers,
        json={
            "expected_page_version": source["page"]["version"],
            "tags": ["e2e", "metadata", "linked"],
            "classifications": ["integration-test"],
            "related_page_ids": [target_page_id],
            "media_asset_ids": [asset_id],
        },
    )
    assert metadata_response.status_code == 200, metadata_response.text

    page_response = await gateway_client.get(
        f"/pages/{source_page_id}",
        headers=auth_headers,
    )
    assert page_response.status_code == 200, page_response.text
    page = page_response.json()["page"]

    assert page["tags"] == ["e2e", "metadata", "linked"]
    assert page["classifications"] == ["integration-test"]
    assert target_page_id in page["related_page_ids"]
    assert asset_id in page["media_asset_ids"]


async def test_invalid_page_mutation_payloads_are_rejected(
    gateway_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    create_cases = [
        {},
        {
            "slug": "",
            "type": "Anomaly",
            "visibility": "Public",
            "title": "Invalid",
            "content": "Invalid empty slug.",
        },
        {
            "slug": f"e2e-invalid-{uuid4().hex[:8]}",
            "type": "NotAType",
            "visibility": "Public",
            "title": "Invalid",
            "content": "Invalid type.",
        },
        {
            "slug": f"e2e-invalid-{uuid4().hex[:8]}",
            "type": "Anomaly",
            "visibility": "NotAVisibility",
            "title": "Invalid",
            "content": "Invalid visibility.",
        },
    ]

    for payload in create_cases:
        response = await gateway_client.post(
            "/pages",
            headers=auth_headers,
            json=payload,
        )
        assert response.status_code in {400, 422}, response.text

    page = await create_published_page(
        gateway_client,
        auth_headers,
        slug_prefix="e2e-invalid-status",
    )
    page_id = page["page"]["id"]

    invalid_status_response = await gateway_client.post(
        f"/pages/{page_id}/status",
        headers=auth_headers,
        json={
            "expected_page_version": page["page"]["version"],
            "status": "DefinitelyNotAStatus",
        },
    )
    assert invalid_status_response.status_code in {400, 422}, invalid_status_response.text