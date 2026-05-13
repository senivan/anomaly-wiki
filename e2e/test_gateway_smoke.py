import httpx

from helpers import create_published_page


async def test_gateway_auth_encyclopedia_media_and_search_smoke(
    gateway_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    ready_response = await gateway_client.get("/ready")
    assert ready_response.status_code == 200, ready_response.text

    published = await create_published_page(gateway_client, auth_headers, slug_prefix="e2e-burner")
    page_id = published["page"]["id"]

    read_response = await gateway_client.get(f"/pages/{page_id}", headers=auth_headers)
    assert read_response.status_code == 200, read_response.text
    assert read_response.json()["page"]["slug"] == published["e2e_slug"]

    metadata_response = await gateway_client.put(
        f"/pages/{page_id}/metadata",
        headers=auth_headers,
        json={
            "expected_page_version": published["page"]["version"],
            "tags": ["e2e", "burner"],
            "classifications": ["ci-smoke"],
            "related_page_ids": [],
            "media_asset_ids": [],
        },
    )
    assert metadata_response.status_code == 200, metadata_response.text
    assert metadata_response.json()["page"]["tags"] == ["e2e", "burner"]

    upload_response = await gateway_client.post(
        "/media",
        headers=auth_headers,
        files={"file": ("e2e-note.txt", b"zone smoke test artifact", "text/plain")},
    )
    assert upload_response.status_code == 201, upload_response.text
    asset_id = upload_response.json()["id"]

    media_response = await gateway_client.get(f"/media/{asset_id}", headers=auth_headers)
    assert media_response.status_code == 200, media_response.text
    assert media_response.json()["filename"] == "e2e-note.txt"

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
    assert object_response.content == b"zone smoke test artifact"

    search_response = await gateway_client.get("/search", params={"q": "burner"})
    assert search_response.status_code == 200, search_response.text
    search_body = search_response.json()
    assert "total" in search_body
    assert "hits" in search_body
