from __future__ import annotations

from uuid import uuid4

import httpx


async def test_media_edge_cases_and_real_object_downloads(
    gateway_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    empty_response = await gateway_client.post(
        "/media",
        headers=auth_headers,
        files={"file": ("empty.txt", b"", "text/plain")},
    )
    assert empty_response.status_code == 400, empty_response.text

    overlong_name = "a" * 256 + ".txt"
    overlong_response = await gateway_client.post(
        "/media",
        headers=auth_headers,
        files={"file": (overlong_name, b"content", "text/plain")},
    )
    assert overlong_response.status_code == 400, overlong_response.text

    traversal_response = await gateway_client.post(
        "/media",
        headers=auth_headers,
        files={"file": ("../../field-note.txt", b"path safe", "text/plain")},
    )
    assert traversal_response.status_code == 201, traversal_response.text
    traversal_asset = traversal_response.json()
    assert traversal_asset["filename"] == "field-note.txt"
    assert traversal_asset["storage_path"].endswith("/field-note.txt")

    first_response = await gateway_client.post(
        "/media",
        headers=auth_headers,
        files={"file": ("duplicate.txt", b"first", "text/plain")},
    )
    second_response = await gateway_client.post(
        "/media",
        headers=auth_headers,
        files={"file": ("duplicate.txt", b"second", "text/plain")},
    )
    assert first_response.status_code == 201, first_response.text
    assert second_response.status_code == 201, second_response.text
    first_asset = first_response.json()
    second_asset = second_response.json()
    assert first_asset["id"] != second_asset["id"]
    assert first_asset["storage_path"] != second_asset["storage_path"]

    payload = (f"large-e2e-{uuid4()}-".encode()) * 200_000
    large_response = await gateway_client.post(
        "/media",
        headers=auth_headers,
        files={"file": ("large.bin", payload, "application/octet-stream")},
    )
    assert large_response.status_code == 201, large_response.text
    large_asset = large_response.json()
    assert large_asset["size_bytes"] == len(payload)

    download_response = await gateway_client.get(
        f"/media/{large_asset['id']}/download-url",
        headers=auth_headers,
    )
    assert download_response.status_code == 200, download_response.text
    object_response = await gateway_client.get(download_response.json()["url"])
    assert object_response.status_code == 200, object_response.text
    assert object_response.content == payload


async def test_missing_media_asset_returns_404_through_gateway(
    gateway_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    missing_id = uuid4()
    metadata_response = await gateway_client.get(f"/media/{missing_id}", headers=auth_headers)
    download_response = await gateway_client.get(
        f"/media/{missing_id}/download-url",
        headers=auth_headers,
    )

    assert metadata_response.status_code == 404, metadata_response.text
    assert download_response.status_code == 404, download_response.text
