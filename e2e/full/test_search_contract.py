from __future__ import annotations

from uuid import uuid4

import httpx

from helpers import search_document, seed_search_document


async def test_search_public_contract_filters_private_and_unpublished_documents(
    gateway_client: httpx.AsyncClient,
) -> None:
    public_doc = search_document(
        slug=f"e2e-public-{uuid4().hex[:8]}",
        title="E2E Search Public Contract",
        status="Published",
        visibility="Public",
        tags=["e2e-contract", "public"],
        aliases=["contract-public-alias"],
    )
    internal_doc = search_document(
        slug=f"e2e-internal-{uuid4().hex[:8]}",
        title="E2E Search Internal Contract",
        status="Published",
        visibility="Internal",
        tags=["e2e-contract", "internal"],
    )
    draft_doc = search_document(
        slug=f"e2e-draft-{uuid4().hex[:8]}",
        title="E2E Search Draft Contract",
        status="Draft",
        visibility="Public",
        tags=["e2e-contract", "draft"],
    )

    await seed_search_document(public_doc)
    await seed_search_document(internal_doc)
    await seed_search_document(draft_doc)

    response = await gateway_client.get(
        "/search",
        params={"q": "Contract", "tags": "e2e-contract"},
    )
    assert response.status_code == 200, response.text

    body = response.json()
    slugs = {hit["slug"] for hit in body["hits"]}

    assert public_doc["slug"] in slugs
    assert internal_doc["slug"] not in slugs
    assert draft_doc["slug"] not in slugs


async def test_search_authenticated_contract_can_read_internal_scope(
    gateway_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    internal_doc = search_document(
        slug=f"e2e-auth-internal-{uuid4().hex[:8]}",
        title="E2E Authenticated Internal Contract",
        status="Draft",
        visibility="Internal",
        tags=["e2e-auth-contract"],
        type_="Researcher Note",
    )
    await seed_search_document(internal_doc)

    anonymous_response = await gateway_client.get(
        "/search",
        params={"q": "Authenticated", "tags": "e2e-auth-contract"},
    )
    assert anonymous_response.status_code == 200, anonymous_response.text
    assert anonymous_response.json()["hits"] == []

    authenticated_response = await gateway_client.get(
        "/search",
        headers=auth_headers,
        params={
            "q": "Authenticated",
            "tags": "e2e-auth-contract",
            "visibility": "Internal",
            "status": "Draft",
        },
    )
    assert authenticated_response.status_code == 200, authenticated_response.text

    slugs = {hit["slug"] for hit in authenticated_response.json()["hits"]}
    assert internal_doc["slug"] in slugs


async def test_search_suggest_uses_titles_and_aliases(
    gateway_client: httpx.AsyncClient,
) -> None:
    doc = search_document(
        slug=f"e2e-suggest-{uuid4().hex[:8]}",
        title="E2E Suggestion Contract",
        status="Published",
        visibility="Public",
        tags=["e2e-suggest"],
        aliases=["weird-suggestion-alias"],
    )
    await seed_search_document(doc)

    title_response = await gateway_client.get(
        "/search/suggest",
        params={"q": "Suggest"},
    )
    assert title_response.status_code == 200, title_response.text
    assert "E2E Suggestion Contract" in title_response.json()["suggestions"]

    alias_response = await gateway_client.get(
        "/search/suggest",
        params={"q": "weird-suggestion"},
    )
    assert alias_response.status_code == 200, alias_response.text
    assert "E2E Suggestion Contract" in alias_response.json()["suggestions"]