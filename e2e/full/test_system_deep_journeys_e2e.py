from __future__ import annotations

import asyncio
from uuid import uuid4

import httpx

from helpers import (
    assert_gateway_error,
    compose_stop,
    compose_up,
    create_draft_revision,
    create_page,
    download_media_asset,
    publish_revision,
    transition_page_status,
    update_page_metadata,
    upload_media_asset,
    wait_for_gateway_ready,
    wait_for_search_absence,
    wait_for_search_hit,
)


async def _search_slugs(
    client: httpx.AsyncClient,
    *,
    q: str,
    headers: dict[str, str] | None = None,
    params: dict[str, str] | None = None,
) -> tuple[int, list[str]]:
    response = await client.get("/search", headers=headers, params={"q": q, **(params or {})})
    assert response.status_code == 200, response.text
    body = response.json()
    return body["total"], [hit["slug"] for hit in body["hits"]]


async def _wait_for_search_hit_title(
    client: httpx.AsyncClient,
    *,
    slug: str,
    q: str,
    title: str,
    headers: dict[str, str] | None = None,
    params: dict[str, str] | None = None,
    timeout_seconds: float = 60.0,
    interval_seconds: float = 2.0,
) -> dict:
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    last_hits: list[dict] = []

    while asyncio.get_running_loop().time() <= deadline:
        response = await client.get("/search", headers=headers, params={"q": q, **(params or {})})
        assert response.status_code == 200, response.text
        last_hits = response.json()["hits"]
        for hit in last_hits:
            if hit["slug"] == slug and hit["title"] == title:
                return hit
        await asyncio.sleep(interval_seconds)

    raise AssertionError(f"Search hit {slug} never reached title {title}. Last hits: {last_hits}")


async def _wait_for_search_total(
    client: httpx.AsyncClient,
    *,
    q: str,
    minimum_total: int,
    params: dict[str, str] | None = None,
    timeout_seconds: float = 60.0,
    interval_seconds: float = 2.0,
) -> None:
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    last_total: int | None = None

    while asyncio.get_running_loop().time() <= deadline:
        total, _ = await _search_slugs(client, q=q, params=params)
        last_total = total
        if total >= minimum_total:
            return
        await asyncio.sleep(interval_seconds)

    raise AssertionError(f"Search total for {q} stayed below {minimum_total}. Last total: {last_total}")


async def test_draft_without_parent_uses_current_draft_lineage(
    gateway_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    created = await create_page(
        gateway_client,
        auth_headers,
        slug_prefix="e2e-deep-lineage",
        title="E2E Deep Lineage Initial",
        content="Initial lineage content.",
    )
    second = await create_draft_revision(
        gateway_client,
        auth_headers,
        created,
        title="E2E Deep Lineage Second",
        content="Second lineage content.",
    )
    third = await create_draft_revision(
        gateway_client,
        auth_headers,
        second,
        title="E2E Deep Lineage Third",
        content="Third lineage content.",
    )

    response = await gateway_client.get(
        f"/pages/{created['page']['id']}/revisions/{third['revision']['id']}",
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    lineage = response.json()["lineage"]
    assert [revision["id"] for revision in lineage] == [
        third["revision"]["id"],
        second["revision"]["id"],
        created["revision"]["id"],
    ]


async def test_unpublished_draft_does_not_replace_published_search_result(
    gateway_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    suffix = uuid4().hex[:8]
    original_title = f"E2E Deep Published Original {suffix}"
    draft_title = f"E2E Deep Unpublished Draft {suffix}"
    created = await create_page(
        gateway_client,
        auth_headers,
        slug_prefix="e2e-deep-unpublished",
        title=original_title,
        content="Published original content.",
    )
    published = await publish_revision(gateway_client, auth_headers, created)
    await wait_for_search_hit(gateway_client, slug=created["e2e_slug"], q=original_title)

    await create_draft_revision(
        gateway_client,
        auth_headers,
        published,
        title=draft_title,
        content="Unpublished draft content should stay private.",
    )

    hit = await wait_for_search_hit(gateway_client, slug=created["e2e_slug"], q=original_title)
    assert hit["title"] == original_title
    await wait_for_search_absence(
        gateway_client,
        slug=created["e2e_slug"],
        q=draft_title,
        timeout_seconds=8.0,
        interval_seconds=1.0,
    )


async def test_publishing_second_draft_updates_public_search_result(
    gateway_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    suffix = uuid4().hex[:8]
    original_title = f"E2E Deep Old Published {suffix}"
    updated_title = f"E2E Deep New Published {suffix}"
    created = await create_page(
        gateway_client,
        auth_headers,
        slug_prefix="e2e-deep-publish-update",
        title=original_title,
        content="Old public content.",
    )
    published = await publish_revision(gateway_client, auth_headers, created)
    await wait_for_search_hit(gateway_client, slug=created["e2e_slug"], q=original_title)

    draft = await create_draft_revision(
        gateway_client,
        auth_headers,
        published,
        title=updated_title,
        content="New public content.",
    )
    await publish_revision(gateway_client, auth_headers, draft)

    hit = await _wait_for_search_hit_title(
        gateway_client,
        slug=created["e2e_slug"],
        q=updated_title,
        title=updated_title,
    )
    assert hit["title"] == updated_title


async def test_revert_creates_draft_without_changing_public_search(
    gateway_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    suffix = uuid4().hex[:8]
    initial_token = f"initial-only-{suffix}"
    initial_title = f"E2E Deep Revert {initial_token}"
    published_title = f"E2E Deep Revert Published {suffix}"
    created = await create_page(
        gateway_client,
        auth_headers,
        slug_prefix="e2e-deep-revert-draft",
        title=initial_title,
        content=f"{initial_token} revert content.",
    )
    draft = await create_draft_revision(
        gateway_client,
        auth_headers,
        created,
        title=published_title,
        content="Published revert content.",
    )
    published = await publish_revision(gateway_client, auth_headers, draft)
    await wait_for_search_hit(gateway_client, slug=created["e2e_slug"], q=published_title)

    revert_response = await gateway_client.post(
        f"/pages/{created['page']['id']}/revert",
        headers=auth_headers,
        json={
            "expected_page_version": published["page"]["version"],
            "revision_id": created["revision"]["id"],
        },
    )
    assert revert_response.status_code == 201, revert_response.text
    reverted = revert_response.json()
    assert reverted["revision"]["title"] == initial_title

    hit = await wait_for_search_hit(gateway_client, slug=created["e2e_slug"], q=published_title)
    assert hit["title"] == published_title


async def test_publishing_reverted_draft_restores_initial_search_content(
    gateway_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    suffix = uuid4().hex[:8]
    initial_token = f"restore-initial-{suffix}"
    initial_title = f"E2E Deep Restore {initial_token}"
    changed_title = f"E2E Deep Restore Changed {suffix}"
    created = await create_page(
        gateway_client,
        auth_headers,
        slug_prefix="e2e-deep-revert-publish",
        title=initial_title,
        content=f"{initial_token} restore content.",
    )
    draft = await create_draft_revision(
        gateway_client,
        auth_headers,
        created,
        title=changed_title,
        content="Changed restore content.",
    )
    published = await publish_revision(gateway_client, auth_headers, draft)
    await wait_for_search_hit(gateway_client, slug=created["e2e_slug"], q=changed_title)

    revert_response = await gateway_client.post(
        f"/pages/{created['page']['id']}/revert",
        headers=auth_headers,
        json={
            "expected_page_version": published["page"]["version"],
            "revision_id": created["revision"]["id"],
        },
    )
    assert revert_response.status_code == 201, revert_response.text
    reverted = revert_response.json()
    reverted["e2e_slug"] = created["e2e_slug"]
    await publish_revision(gateway_client, auth_headers, reverted)

    hit = await _wait_for_search_hit_title(
        gateway_client,
        slug=created["e2e_slug"],
        q=initial_token,
        title=initial_title,
    )
    assert hit["title"] == initial_title


async def test_archived_page_can_return_to_draft_and_be_republished(
    gateway_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    title = f"E2E Deep Archive Restore {uuid4().hex[:8]}"
    created = await create_page(
        gateway_client,
        auth_headers,
        slug_prefix="e2e-deep-archive-restore",
        title=title,
        content="Archive restore content.",
    )
    published = await publish_revision(gateway_client, auth_headers, created)
    await wait_for_search_hit(gateway_client, slug=created["e2e_slug"], q=title)

    archived = await transition_page_status(gateway_client, auth_headers, published, status="Archived")
    await wait_for_search_absence(gateway_client, slug=created["e2e_slug"], q=title)
    draft = await transition_page_status(gateway_client, auth_headers, archived, status="Draft")
    await wait_for_search_absence(
        gateway_client,
        slug=created["e2e_slug"],
        q=title,
        timeout_seconds=8.0,
        interval_seconds=1.0,
    )

    draft["revision"] = draft["current_draft_revision"]
    await publish_revision(gateway_client, auth_headers, draft)
    await wait_for_search_hit(gateway_client, slug=created["e2e_slug"], q=title)


async def test_redacted_page_is_removed_and_cannot_return_to_draft(
    gateway_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    title = f"E2E Deep Redacted Terminal {uuid4().hex[:8]}"
    created = await create_page(
        gateway_client,
        auth_headers,
        slug_prefix="e2e-deep-redacted",
        title=title,
        content="Redacted terminal content.",
    )
    published = await publish_revision(gateway_client, auth_headers, created)
    await wait_for_search_hit(gateway_client, slug=created["e2e_slug"], q=title)

    redacted = await transition_page_status(gateway_client, auth_headers, published, status="Redacted")
    await wait_for_search_absence(gateway_client, slug=created["e2e_slug"], q=title)

    response = await gateway_client.post(
        f"/pages/{created['page']['id']}/status",
        headers=auth_headers,
        json={"expected_page_version": redacted["page"]["version"], "status": "Draft"},
    )
    assert response.status_code == 400, response.text


async def test_search_type_filter_separates_same_query_across_page_types(
    gateway_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    token = f"deep-type-{uuid4().hex[:8]}"
    pages = []
    for page_type in ("Article", "Incident", "Researcher Note"):
        created = await create_page(
            gateway_client,
            auth_headers,
            slug_prefix=f"e2e-{page_type.lower().replace(' ', '-')}",
            title=f"E2E {page_type} {token}",
            content=f"{token} content for {page_type}.",
            type_=page_type,
        )
        published = await publish_revision(gateway_client, auth_headers, created)
        pages.append((page_type, published["e2e_slug"]))

    for page_type, slug in pages:
        hit = await wait_for_search_hit(
            gateway_client,
            slug=slug,
            q=token,
            params={"type": page_type},
        )
        assert hit["type"] == page_type


async def test_metadata_tags_are_trimmed_deduped_and_empty_values_removed(
    gateway_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    created = await create_page(
        gateway_client,
        auth_headers,
        slug_prefix="e2e-deep-tags",
        title="E2E Deep Tag Normalization",
        content="Tag normalization content.",
    )
    updated = await update_page_metadata(
        gateway_client,
        auth_headers,
        created,
        tags=["  alpha  ", "", "alpha", " beta ", "beta"],
        classifications=["  class-a ", "class-a", "", "class-b"],
    )
    assert updated["page"]["tags"] == ["alpha", "beta"]
    assert updated["page"]["classifications"] == ["class-a", "class-b"]


async def test_normalized_metadata_tags_propagate_to_search_filtering(
    gateway_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    suffix = uuid4().hex[:8]
    title = f"E2E Deep Normalized Search Tags {suffix}"
    tag = f"normalized-{suffix}"
    created = await create_page(
        gateway_client,
        auth_headers,
        slug_prefix="e2e-deep-normalized-tags",
        title=title,
        content="Normalized tags search content.",
    )
    published = await publish_revision(gateway_client, auth_headers, created)
    await update_page_metadata(
        gateway_client,
        auth_headers,
        published,
        tags=[f"  {tag}  ", tag],
    )
    await wait_for_search_hit(gateway_client, slug=created["e2e_slug"], q=title, params={"tags": tag})


async def test_replacing_metadata_tags_removes_old_search_filter(
    gateway_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    suffix = uuid4().hex[:8]
    title = f"E2E Deep Replace Tags {suffix}"
    old_tag = f"old-{suffix}"
    new_tag = f"new-{suffix}"
    created = await create_page(
        gateway_client,
        auth_headers,
        slug_prefix="e2e-deep-replace-tags",
        title=title,
        content="Replace metadata tags content.",
    )
    published = await publish_revision(gateway_client, auth_headers, created)
    old_metadata = await update_page_metadata(gateway_client, auth_headers, published, tags=[old_tag])
    await wait_for_search_hit(gateway_client, slug=created["e2e_slug"], q=title, params={"tags": old_tag})
    await update_page_metadata(gateway_client, auth_headers, old_metadata, tags=[new_tag])

    await wait_for_search_hit(gateway_client, slug=created["e2e_slug"], q=title, params={"tags": new_tag})
    await wait_for_search_absence(gateway_client, slug=created["e2e_slug"], q=title, params={"tags": old_tag})


async def test_related_page_ids_are_deduped_and_linked_pages_remain_readable(
    gateway_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    source = await create_page(
        gateway_client,
        auth_headers,
        slug_prefix="e2e-deep-source",
        title="E2E Deep Related Source",
        content="Related source content.",
    )
    first = await create_page(
        gateway_client,
        auth_headers,
        slug_prefix="e2e-deep-related-first",
        title="E2E Deep Related First",
        content="Related first content.",
    )
    second = await create_page(
        gateway_client,
        auth_headers,
        slug_prefix="e2e-deep-related-second",
        title="E2E Deep Related Second",
        content="Related second content.",
    )
    updated = await update_page_metadata(
        gateway_client,
        auth_headers,
        source,
        related_page_ids=[first["page"]["id"], second["page"]["id"], first["page"]["id"]],
    )
    assert updated["page"]["related_page_ids"] == [first["page"]["id"], second["page"]["id"]]

    for related in (first, second):
        response = await gateway_client.get(f"/pages/{related['page']['id']}", headers=auth_headers)
        assert response.status_code == 200, response.text


async def test_media_asset_ids_are_deduped_and_linked_media_downloads(
    gateway_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    page = await create_page(
        gateway_client,
        auth_headers,
        slug_prefix="e2e-deep-media-dedupe",
        title="E2E Deep Media Dedupe",
        content="Media dedupe content.",
    )
    first_payload = b"first linked media"
    second_payload = b"second linked media"
    first = await upload_media_asset(
        gateway_client,
        auth_headers,
        filename="first-linked.txt",
        payload=first_payload,
    )
    second = await upload_media_asset(
        gateway_client,
        auth_headers,
        filename="second-linked.txt",
        payload=second_payload,
    )
    updated = await update_page_metadata(
        gateway_client,
        auth_headers,
        page,
        media_asset_ids=[first["id"], second["id"], first["id"]],
    )
    assert updated["page"]["media_asset_ids"] == [first["id"], second["id"]]
    assert await download_media_asset(gateway_client, auth_headers, first["id"]) == first_payload
    assert await download_media_asset(gateway_client, auth_headers, second["id"]) == second_payload


async def test_markdown_content_is_indexed_as_plain_searchable_text(
    gateway_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    suffix = uuid4().hex[:8]
    title = f"E2E Deep Markdown {suffix}"
    token = f"markdown-token-{suffix}"
    created = await create_page(
        gateway_client,
        auth_headers,
        slug_prefix="e2e-deep-markdown",
        title=title,
        content=f"# Heading\n\nThis **bold** note includes `{token}` inside markdown.",
    )
    await publish_revision(gateway_client, auth_headers, created)
    hit = await wait_for_search_hit(gateway_client, slug=created["e2e_slug"], q=token)
    assert hit["slug"] == created["e2e_slug"]


async def test_internal_published_suggestions_are_hidden_anonymously(
    gateway_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    title = f"E2E Deep Internal Suggest {uuid4().hex[:8]}"
    created = await create_page(
        gateway_client,
        auth_headers,
        slug_prefix="e2e-deep-internal-suggest",
        title=title,
        content="Internal suggestion content.",
        visibility="Internal",
        type_="Researcher Note",
    )
    await publish_revision(gateway_client, auth_headers, created)

    response = await gateway_client.get("/search/suggest", params={"q": title[:24]})
    assert response.status_code == 200, response.text
    assert title not in response.json()["suggestions"]


async def test_internal_published_suggestions_are_visible_to_authenticated_search(
    gateway_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    title = f"E2E Deep Auth Suggest {uuid4().hex[:8]}"
    created = await create_page(
        gateway_client,
        auth_headers,
        slug_prefix="e2e-deep-auth-suggest",
        title=title,
        content="Authenticated suggestion content.",
        visibility="Internal",
        type_="Researcher Note",
    )
    await publish_revision(gateway_client, auth_headers, created)
    await wait_for_search_hit(
        gateway_client,
        slug=created["e2e_slug"],
        q=title,
        headers=auth_headers,
        params={"visibility": "Internal"},
    )

    response = await gateway_client.get("/search/suggest", headers=auth_headers, params={"q": title[:24]})
    assert response.status_code == 200, response.text
    assert title in response.json()["suggestions"]


async def test_search_pagination_returns_non_overlapping_pages_and_total(
    gateway_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    token = f"pagetoken{uuid4().hex}"
    expected_slugs: set[str] = set()
    for index in range(12):
        created = await create_page(
            gateway_client,
            auth_headers,
            slug_prefix="e2e-deep-pagination",
            title=f"E2E Deep Pagination {token} {index:02d}",
            content=f"{token} pagination content {index:02d}.",
        )
        expected_slugs.add(created["e2e_slug"])
        await publish_revision(gateway_client, auth_headers, created)

    await _wait_for_search_total(gateway_client, q=token, minimum_total=12, params={"size": "50"})
    total0, page0 = await _search_slugs(gateway_client, q=token, params={"page": "0", "size": "5"})
    total1, page1 = await _search_slugs(gateway_client, q=token, params={"page": "1", "size": "5"})
    assert total0 >= 12
    assert total1 == total0
    assert set(page0).isdisjoint(page1)
    assert set(page0 + page1).issubset(expected_slugs)


async def test_authenticated_status_filters_distinguish_active_and_terminal_pages(
    gateway_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    token = f"deep-status-{uuid4().hex[:8]}"
    created_by_status: dict[str, dict] = {}
    for status in ("Draft", "Review", "Published", "Archived", "Redacted"):
        page = await create_page(
            gateway_client,
            auth_headers,
            slug_prefix=f"e2e-deep-status-{status.lower()}",
            title=f"E2E Deep Status {status} {token}",
            content=f"{token} content for status {status}.",
            visibility="Internal",
        )
        if status == "Review":
            page = await transition_page_status(gateway_client, auth_headers, page, status="Review")
        elif status == "Published":
            page = await publish_revision(gateway_client, auth_headers, page)
        elif status == "Archived":
            page = await publish_revision(gateway_client, auth_headers, page)
            page = await transition_page_status(gateway_client, auth_headers, page, status="Archived")
        elif status == "Redacted":
            page = await publish_revision(gateway_client, auth_headers, page)
            page = await transition_page_status(gateway_client, auth_headers, page, status="Redacted")
        created_by_status[status] = page

    for status in ("Draft", "Review", "Published"):
        await wait_for_search_hit(
            gateway_client,
            slug=created_by_status[status]["e2e_slug"],
            q=token,
            headers=auth_headers,
            params={"status": status, "visibility": "Internal"},
        )
    for status in ("Archived", "Redacted"):
        await wait_for_search_absence(
            gateway_client,
            slug=created_by_status[status]["e2e_slug"],
            q=token,
            headers=auth_headers,
            params={"status": status, "visibility": "Internal"},
        )


async def test_anonymous_search_with_spoofed_internal_headers_cannot_see_internal_documents(
    gateway_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    title = f"E2E Deep Spoof Anonymous {uuid4().hex[:8]}"
    created = await create_page(
        gateway_client,
        auth_headers,
        slug_prefix="e2e-deep-spoof-anon",
        title=title,
        content="Spoof anonymous content.",
        visibility="Internal",
        type_="Researcher Note",
    )
    await publish_revision(gateway_client, auth_headers, created)

    response = await gateway_client.get(
        "/search",
        headers={
            "X-Authenticated-Source": "api-gateway",
            "X-Authenticated-User-Role": "Researcher",
            "X-Internal-Token": "e2e-internal-token",
        },
        params={"q": title, "visibility": "Internal"},
    )
    assert response.status_code == 200, response.text
    assert all(hit["slug"] != created["e2e_slug"] for hit in response.json()["hits"])


async def test_valid_token_internal_search_ignores_spoofed_external_headers(
    gateway_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    title = f"E2E Deep Spoof Auth {uuid4().hex[:8]}"
    created = await create_page(
        gateway_client,
        auth_headers,
        slug_prefix="e2e-deep-spoof-auth",
        title=title,
        content="Spoof authenticated content.",
        visibility="Internal",
        type_="Researcher Note",
    )
    await publish_revision(gateway_client, auth_headers, created)
    headers = {
        **auth_headers,
        "X-Authenticated-Source": "not-api-gateway",
        "X-Authenticated-User-Role": "anonymous",
        "X-Internal-Token": "wrong",
    }
    hit = await wait_for_search_hit(
        gateway_client,
        slug=created["e2e_slug"],
        q=title,
        headers=headers,
        params={"visibility": "Internal"},
    )
    assert hit["visibility"] == "Internal"


async def test_gateway_rejects_non_multipart_media_upload_with_error_contract(
    gateway_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    response = await gateway_client.post(
        "/media",
        headers=auth_headers,
        json={"filename": "not-multipart.txt", "content": "not multipart"},
    )
    assert_gateway_error(response, 415, "unsupported_media_upload_content_type")


async def test_media_upload_without_explicit_content_type_downloads_bytes(
    gateway_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    payload = b"implicit content type media"
    asset = await upload_media_asset(
        gateway_client,
        auth_headers,
        filename="implicit.bin",
        payload=payload,
        content_type=None,
    )
    assert asset["content_type"] == "application/octet-stream"
    assert await download_media_asset(gateway_client, auth_headers, asset["id"]) == payload


async def test_search_indexer_outage_buffers_page_event_until_recovery(
    gateway_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    title = f"E2E Deep Indexer Outage {uuid4().hex[:8]}"
    try:
        compose_stop("search-indexer")
        created = await create_page(
            gateway_client,
            auth_headers,
            slug_prefix="e2e-deep-indexer-outage",
            title=title,
            content="Indexer outage buffered event content.",
        )
        await publish_revision(gateway_client, auth_headers, created)
        await wait_for_search_absence(
            gateway_client,
            slug=created["e2e_slug"],
            q=title,
            timeout_seconds=8.0,
            interval_seconds=1.0,
        )
    finally:
        compose_up("search-indexer")
        await wait_for_gateway_ready(gateway_client, timeout_seconds=120.0)

    await wait_for_search_hit(gateway_client, slug=created["e2e_slug"], q=title, timeout_seconds=120.0)


async def test_rabbitmq_outage_drops_current_event_but_recovers_for_later_pages(
    gateway_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    lost_title = f"E2E Deep Rabbit Lost {uuid4().hex[:8]}"
    recovered_title = f"E2E Deep Rabbit Recovered {uuid4().hex[:8]}"
    try:
        compose_stop("rabbitmq")
        lost = await create_page(
            gateway_client,
            auth_headers,
            slug_prefix="e2e-deep-rabbit-lost",
            title=lost_title,
            content="RabbitMQ outage lost event content.",
        )
        await publish_revision(gateway_client, auth_headers, lost)
        await wait_for_search_absence(
            gateway_client,
            slug=lost["e2e_slug"],
            q=lost_title,
            timeout_seconds=8.0,
            interval_seconds=1.0,
        )
    finally:
        compose_up("rabbitmq")
        compose_up("search-indexer")
        await asyncio.sleep(2)
        await wait_for_gateway_ready(gateway_client, timeout_seconds=120.0)

    recovered = await create_page(
        gateway_client,
        auth_headers,
        slug_prefix="e2e-deep-rabbit-recovered",
        title=recovered_title,
        content="RabbitMQ recovered event content.",
    )
    await publish_revision(gateway_client, auth_headers, recovered)
    await wait_for_search_hit(gateway_client, slug=recovered["e2e_slug"], q=recovered_title, timeout_seconds=120.0)
