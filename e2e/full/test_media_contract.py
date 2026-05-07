from __future__ import annotations

from uuid import uuid4

import httpx


async def test_media_metadata_download_and_missing_objects_contract(
    gateway_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    payload = b"media contract payload"

    upload_response = await gateway_client.post(
        "/media",
        headers=auth_headers,
        files={"file": ("contract.txt", payload, "text/plain")},
    )
    assert upload_response.status_code == 201, upload_response.text

    uploaded = upload_response.json()
    asset_id = uploaded["id"]
    assert uploaded["filename"] == "contract.txt"
    assert uploaded["content_type"] == "text/plain"
    assert uploaded["size_bytes"] == len(payload)

    metadata_response = await gateway_client.get(
        f"/media/{asset_id}",
        headers=auth_headers,
    )
    assert metadata_response.status_code == 200, metadata_response.text
    metadata = metadata_response.json()
    assert metadata["id"] == asset_id
    assert metadata["filename"] == "contract.txt"

    download_response = await gateway_client.get(
        f"/media/{asset_id}/download-url",
        headers=auth_headers,
    )
    assert download_response.status_code == 200, download_response.text
    download_body = download_response.json()
    assert download_body["asset_id"] == asset_id
    assert download_body["url"]

    object_response = await gateway_client.get(download_body["url"])
    assert object_response.status_code == 200, object_response.text
    assert object_response.content == payload

    missing_id = uuid4()
    missing_metadata = await gateway_client.get(
        f"/media/{missing_id}",
        headers=auth_headers,
    )
    missing_download = await gateway_client.get(
        f"/media/{missing_id}/download-url",
        headers=auth_headers,
    )

    assert missing_metadata.status_code == 404, missing_metadata.text
    assert missing_download.status_code == 404, missing_download.text


async def test_media_upload_filename_sanitization_and_duplicate_storage_paths(
    gateway_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
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


async def test_media_rejects_empty_overlong_and_oversized_uploads(
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

    oversized = b"x" * (25 * 1024 * 1024 + 1)
    oversized_response = await gateway_client.post(
        "/media",
        headers=auth_headers,
        files={"file": ("oversized.bin", oversized, "application/octet-stream")},
    )
    assert oversized_response.status_code == 413, oversized_response.text