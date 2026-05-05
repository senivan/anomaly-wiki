from __future__ import annotations

import asyncio
import os

import httpx
import pytest

from helpers import create_published_page


pytestmark = pytest.mark.skipif(
    os.getenv("E2E_ENABLE_SEARCH_INDEXING") != "1",
    reason="search-indexer is not part of the current main compose stack",
)


async def test_published_page_eventually_appears_in_search(
    gateway_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    page = await create_published_page(
        gateway_client,
        auth_headers,
        slug_prefix="e2e-indexed",
    )
    expected_slug = page["e2e_slug"]

    for _ in range(30):
        response = await gateway_client.get("/search", params={"q": "Burner"})
        assert response.status_code == 200, response.text
        hits = response.json()["hits"]
        if any(hit["slug"] == expected_slug for hit in hits):
            return
        await asyncio.sleep(2)

    pytest.fail(f"Published page {expected_slug} did not appear in search results")
