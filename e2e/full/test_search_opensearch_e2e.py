from __future__ import annotations

from uuid import uuid4

import httpx

from helpers import search_document, seed_search_document


async def test_real_opensearch_public_filters_highlights_and_suggest(
    gateway_client: httpx.AsyncClient,
) -> None:
    public_doc = search_document(
        slug=f"e2e-public-search-{uuid4().hex[:8]}",
        title="E2E Public Burner",
        status="Published",
        visibility="Public",
        tags=["e2e-search", "public"],
        aliases=["burner-alias"],
    )
    internal_doc = search_document(
        slug=f"e2e-internal-search-{uuid4().hex[:8]}",
        title="E2E Internal Burner",
        status="Draft",
        visibility="Internal",
        tags=["e2e-search", "internal"],
    )
    await seed_search_document(public_doc)
    await seed_search_document(internal_doc)

    search_response = await gateway_client.get(
        "/search",
        params={"q": "Burner", "tags": "e2e-search", "type": "Anomaly"},
    )
    assert search_response.status_code == 200, search_response.text
    hits = search_response.json()["hits"]
    slugs = {hit["slug"] for hit in hits}
    assert public_doc["slug"] in slugs
    assert internal_doc["slug"] not in slugs
    assert any(hit["snippet"] for hit in hits if hit["slug"] == public_doc["slug"])

    suggest_response = await gateway_client.get("/search/suggest", params={"q": "burner-al"})
    assert suggest_response.status_code == 200, suggest_response.text
    assert "E2E Public Burner" in suggest_response.json()["suggestions"]


async def test_authenticated_internal_search_can_filter_status_and_visibility(
    gateway_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    draft_doc = search_document(
        slug=f"e2e-draft-search-{uuid4().hex[:8]}",
        title="E2E Draft Psi Field",
        status="Draft",
        visibility="Internal",
        tags=["e2e-internal-filter"],
        type_="Researcher Note",
    )
    await seed_search_document(draft_doc)

    anonymous_response = await gateway_client.get(
        "/search",
        params={"q": "Psi", "tags": "e2e-internal-filter"},
    )
    assert anonymous_response.status_code == 200, anonymous_response.text
    assert anonymous_response.json()["hits"] == []

    internal_response = await gateway_client.get(
        "/search",
        headers=auth_headers,
        params={
            "q": "Psi",
            "tags": "e2e-internal-filter",
            "visibility": "Internal",
            "status": "Draft",
        },
    )
    assert internal_response.status_code == 200, internal_response.text
    slugs = {hit["slug"] for hit in internal_response.json()["hits"]}
    assert draft_doc["slug"] in slugs
