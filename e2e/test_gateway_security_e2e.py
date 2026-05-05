from __future__ import annotations

import httpx


async def test_page_routes_reject_missing_and_invalid_tokens(
    gateway_client: httpx.AsyncClient,
) -> None:
    page_id = "11111111-1111-1111-1111-111111111111"

    missing_response = await gateway_client.get(
        f"/pages/{page_id}",
        headers={
            "X-Authenticated-Source": "api-gateway",
            "X-Authenticated-User-Role": "Admin",
        },
    )
    assert missing_response.status_code == 401, missing_response.text
    assert missing_response.json()["error"]["code"] == "missing_bearer_token"

    invalid_response = await gateway_client.get(
        f"/pages/{page_id}",
        headers={"Authorization": "Bearer not-a-valid-token"},
    )
    assert invalid_response.status_code == 401, invalid_response.text
    assert invalid_response.json()["error"]["code"] == "invalid_token"


async def test_media_routes_reject_missing_tokens(
    gateway_client: httpx.AsyncClient,
) -> None:
    asset_id = "11111111-1111-1111-1111-111111111111"

    metadata_response = await gateway_client.get(f"/media/{asset_id}")
    download_response = await gateway_client.get(f"/media/{asset_id}/download-url")
    upload_response = await gateway_client.post(
        "/media",
        files={"file": ("spoof.txt", b"spoof", "text/plain")},
    )

    assert metadata_response.status_code == 401, metadata_response.text
    assert download_response.status_code == 401, download_response.text
    assert upload_response.status_code == 401, upload_response.text


async def test_spoofed_gateway_identity_headers_do_not_authenticate(
    gateway_client: httpx.AsyncClient,
) -> None:
    response = await gateway_client.post(
        "/pages",
        headers={
            "X-Authenticated-Source": "api-gateway",
            "X-Authenticated-User-Id": "11111111-1111-1111-1111-111111111111",
            "X-Authenticated-User-Role": "Admin",
        },
        json={
            "slug": "spoofed-page",
            "type": "Anomaly",
            "visibility": "Public",
            "title": "Spoofed",
            "content": "This should not be accepted.",
        },
    )

    assert response.status_code == 401, response.text
    assert response.json()["error"]["code"] == "missing_bearer_token"


async def test_media_upload_rejects_oversized_payload_before_forwarding(
    gateway_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    oversized = b"x" * (25 * 1024 * 1024 + 1)

    response = await gateway_client.post(
        "/media",
        headers=auth_headers,
        files={"file": ("oversized.bin", oversized, "application/octet-stream")},
    )

    assert response.status_code == 413, response.text
    assert response.json()["error"]["code"] == "media_upload_too_large"
