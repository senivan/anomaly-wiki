from __future__ import annotations

from uuid import uuid4

import httpx
import pytest

from helpers import (
    MINIO_HEALTH_URL,
    OPENSEARCH_BASE_URL,
    assert_gateway_error,
    compose_stop,
    compose_up,
    create_published_page,
    wait_for_gateway_degraded,
    wait_for_gateway_ready,
    wait_for_search_available,
    wait_for_url_ok,
)


async def _create_draft_page(
    gateway_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> dict:
    response = await gateway_client.post(
        "/pages",
        headers=auth_headers,
        json={
            "slug": f"e2e-recovery-{uuid4().hex[:8]}",
            "type": "Anomaly",
            "visibility": "Public",
            "title": "E2E Recovery Draft",
            "summary": "Recovery test draft page.",
            "content": "Recovery test content.",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_invalid_page_uuid_is_rejected_before_upstream_recovery(
    gateway_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    response = await gateway_client.get("/pages/not-a-uuid", headers=auth_headers)
    assert response.status_code == 422, response.text


async def test_invalid_media_uuid_is_rejected_before_upstream_recovery(
    gateway_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    response = await gateway_client.get("/media/not-a-uuid", headers=auth_headers)
    assert response.status_code == 422, response.text


async def test_missing_page_revision_returns_stable_not_found(
    gateway_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    page = await create_published_page(gateway_client, auth_headers, slug_prefix="e2e-missing-revision")
    response = await gateway_client.get(
        f"/pages/{page['page']['id']}/revisions/{uuid4()}",
        headers=auth_headers,
    )
    assert response.status_code == 404, response.text


async def test_publish_missing_revision_recovers_with_not_found_or_conflict(
    gateway_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    page = await _create_draft_page(gateway_client, auth_headers)
    response = await gateway_client.post(
        f"/pages/{page['page']['id']}/publish",
        headers=auth_headers,
        json={
            "expected_page_version": page["page"]["version"],
            "revision_id": str(uuid4()),
        },
    )
    assert response.status_code in {404, 409}, response.text


async def test_revert_missing_revision_recovers_with_not_found_or_conflict(
    gateway_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    page = await _create_draft_page(gateway_client, auth_headers)
    response = await gateway_client.post(
        f"/pages/{page['page']['id']}/revert",
        headers=auth_headers,
        json={
            "expected_page_version": page["page"]["version"],
            "revision_id": str(uuid4()),
        },
    )
    assert response.status_code in {404, 409}, response.text


async def test_status_transition_with_stale_version_returns_conflict(
    gateway_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    page = await _create_draft_page(gateway_client, auth_headers)
    stale_version = page["page"]["version"]

    metadata_response = await gateway_client.put(
        f"/pages/{page['page']['id']}/metadata",
        headers=auth_headers,
        json={
            "expected_page_version": stale_version,
            "tags": ["recovery"],
            "classifications": [],
            "related_page_ids": [],
            "media_asset_ids": [],
        },
    )
    assert metadata_response.status_code == 200, metadata_response.text

    stale_status = await gateway_client.post(
        f"/pages/{page['page']['id']}/status",
        headers=auth_headers,
        json={"expected_page_version": stale_version, "status": "Review"},
    )
    assert stale_status.status_code == 409, stale_status.text


async def test_metadata_self_reference_returns_recoverable_bad_request(
    gateway_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    page = await _create_draft_page(gateway_client, auth_headers)
    response = await gateway_client.put(
        f"/pages/{page['page']['id']}/metadata",
        headers=auth_headers,
        json={
            "expected_page_version": page["page"]["version"],
            "tags": [],
            "classifications": [],
            "related_page_ids": [page["page"]["id"]],
            "media_asset_ids": [],
        },
    )
    assert response.status_code == 400, response.text


async def test_metadata_unknown_related_page_returns_recoverable_bad_request(
    gateway_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    page = await _create_draft_page(gateway_client, auth_headers)
    response = await gateway_client.put(
        f"/pages/{page['page']['id']}/metadata",
        headers=auth_headers,
        json={
            "expected_page_version": page["page"]["version"],
            "tags": [],
            "classifications": [],
            "related_page_ids": [str(uuid4())],
            "media_asset_ids": [],
        },
    )
    assert response.status_code == 400, response.text


async def test_empty_search_query_returns_validation_error(
    gateway_client: httpx.AsyncClient,
) -> None:
    response = await gateway_client.get("/search", params={"q": ""})
    assert response.status_code == 422, response.text


async def test_search_size_above_limit_returns_validation_error(
    gateway_client: httpx.AsyncClient,
) -> None:
    response = await gateway_client.get("/search", params={"q": "recovery", "size": "51"})
    assert response.status_code == 422, response.text


async def test_missing_media_metadata_returns_stable_not_found(
    gateway_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    response = await gateway_client.get(f"/media/{uuid4()}", headers=auth_headers)
    assert response.status_code == 404, response.text


async def test_missing_media_download_url_returns_stable_not_found(
    gateway_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    response = await gateway_client.get(f"/media/{uuid4()}/download-url", headers=auth_headers)
    assert response.status_code == 404, response.text


@pytest.mark.parametrize(
    ("service", "ready_service", "path", "expected_code"),
    [
        ("search-service", "search_service", "/search?q=recovery", "upstream_unavailable"),
        ("media-service", "media_service", "/media/11111111-1111-1111-1111-111111111111", "upstream_unavailable"),
        (
            "encyclopedia-service",
            "encyclopedia_service",
            "/pages/11111111-1111-1111-1111-111111111111",
            "upstream_unavailable",
        ),
    ],
)
async def test_gateway_reports_downstream_outage_and_recovers(
    gateway_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    service: str,
    ready_service: str,
    path: str,
    expected_code: str,
) -> None:
    try:
        compose_stop(service)
        await wait_for_gateway_degraded(gateway_client, service_name=ready_service)

        response = await gateway_client.get(path, headers=auth_headers)
        assert_gateway_error(response, 503, expected_code)
    finally:
        compose_up(service)
        await wait_for_gateway_ready(gateway_client)


async def test_auth_service_outage_reports_degraded_and_recovers(
    gateway_client: httpx.AsyncClient,
) -> None:
    try:
        compose_stop("researcher-auth-service")
        await wait_for_gateway_degraded(gateway_client, service_name="researcher_auth_service")

        response = await gateway_client.get("/auth/jwks")
        assert_gateway_error(response, 503, "upstream_unavailable")
    finally:
        compose_up("researcher-auth-service")
        await wait_for_gateway_ready(gateway_client)


async def test_opensearch_outage_surfaces_search_unavailable_and_recovers(
    gateway_client: httpx.AsyncClient,
) -> None:
    try:
        compose_stop("opensearch")

        response = await gateway_client.get("/search", params={"q": "recovery"})
        body = assert_gateway_error(response, 503, "upstream_server_error")
        assert body["error"]["details"]["service"] == "search-service"
        assert body["error"]["details"]["upstream_status"] == 503
    finally:
        compose_up("opensearch")
        await wait_for_url_ok(OPENSEARCH_BASE_URL, timeout_seconds=120.0)
        await wait_for_gateway_ready(gateway_client, timeout_seconds=120.0)
        await wait_for_search_available(gateway_client, timeout_seconds=120.0)


async def test_minio_outage_surfaces_media_storage_failure_and_recovers(
    gateway_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    try:
        compose_stop("minio")

        response = await gateway_client.post(
            "/media",
            headers=auth_headers,
            files={"file": ("minio-outage.txt", b"minio outage", "text/plain")},
        )
        assert response.status_code >= 500, response.text
    finally:
        compose_up("minio")
        await wait_for_url_ok(MINIO_HEALTH_URL, timeout_seconds=120.0)
        await wait_for_gateway_ready(gateway_client, timeout_seconds=120.0)
