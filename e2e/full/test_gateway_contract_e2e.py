from __future__ import annotations

import httpx
import pytest


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("GET", "/pages/11111111-1111-1111-1111-111111111111", None),
        ("GET", "/pages/11111111-1111-1111-1111-111111111111/revisions", None),
        (
            "GET",
            "/pages/11111111-1111-1111-1111-111111111111/revisions/22222222-2222-2222-2222-222222222222",
            None,
        ),
        (
            "POST",
            "/pages",
            {
                "slug": "missing-auth",
                "type": "Anomaly",
                "visibility": "Public",
                "title": "Missing Auth",
                "content": "Should fail.",
            },
        ),
        (
            "POST",
            "/pages/11111111-1111-1111-1111-111111111111/drafts",
            {
                "expected_page_version": 1,
                "title": "Missing Auth",
                "content": "Should fail.",
            },
        ),
        (
            "PUT",
            "/pages/11111111-1111-1111-1111-111111111111/metadata",
            {
                "expected_page_version": 1,
                "tags": [],
                "classifications": [],
                "related_page_ids": [],
                "media_asset_ids": [],
            },
        ),
        ("GET", "/media/11111111-1111-1111-1111-111111111111", None),
        ("GET", "/media/11111111-1111-1111-1111-111111111111/download-url", None),
    ],
)
async def test_protected_gateway_routes_require_real_bearer_token(
    gateway_client: httpx.AsyncClient,
    method: str,
    path: str,
    payload: dict | None,
) -> None:
    response = await gateway_client.request(
        method,
        path,
        json=payload,
        headers={
            "X-Authenticated-Source": "api-gateway",
            "X-Authenticated-User-Id": "11111111-1111-1111-1111-111111111111",
            "X-Authenticated-User-Role": "Admin",
            "X-Internal-Token": "spoofed-client-token",
        },
    )

    assert response.status_code == 401, response.text


@pytest.mark.parametrize(
    "path",
    [
        "/pages/11111111-1111-1111-1111-111111111111",
        "/media/11111111-1111-1111-1111-111111111111",
        "/search?q=contract",
        "/search/suggest?q=contract",
    ],
)
async def test_invalid_bearer_token_is_rejected_consistently(
    gateway_client: httpx.AsyncClient,
    path: str,
) -> None:
    response = await gateway_client.get(
        path,
        headers={"Authorization": "Bearer not-a-valid-token"},
    )

    assert response.status_code == 401, response.text
    assert response.json()["error"]["code"] == "invalid_token"