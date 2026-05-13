from httpx import ASGITransport, AsyncClient
from tests.conftest import build_search_app, make_os_response


SAMPLE_HIT = {
    "page_id": "abc-123",
    "slug": "fire-anomaly",
    "type": "Anomaly",
    "status": "Published",
    "visibility": "Public",
    "title": "Fire Anomaly",
    "summary": "A burning anomaly near Agroprom.",
    "content_text": "The fire anomaly is deadly.",
    "tags": ["fire", "thermal"],
    "aliases": [],
}


async def test_search_returns_hits_for_public_request():
    app, fake_os = build_search_app(make_os_response([SAMPLE_HIT]))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/search?q=fire")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["hits"][0]["slug"] == "fire-anomaly"
    assert body["hits"][0]["snippet"] != ""


async def test_search_applies_public_filter_when_no_auth_source_header():
    app, fake_os = build_search_app(make_os_response([]))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.get("/search?q=fire")

    call_args = fake_os.search.call_args
    query_body = call_args.kwargs["body"]
    filters = query_body["query"]["bool"]["filter"]
    filter_terms = {list(f.get("term", {}).keys())[0]: list(f.get("term", {}).values())[0]
                   for f in filters if "term" in f}
    assert filter_terms.get("visibility") == "Public"
    assert filter_terms.get("status") == "Published"


async def test_search_omits_visibility_filter_for_researcher():
    app, fake_os = build_search_app(make_os_response([]), internal_token="test-token")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.get(
            "/search?q=fire",
            headers={
                "X-Authenticated-Source": "api-gateway",
                "X-Authenticated-User-Role": "Researcher",
                "X-Internal-Token": "test-token",
            },
        )

    call_args = fake_os.search.call_args
    query_body = call_args.kwargs["body"]
    filters = query_body["query"]["bool"]["filter"]
    filter_keys = [list(f.get("term", {}).keys())[0] for f in filters if "term" in f]
    assert "visibility" not in filter_keys
    assert "status" not in filter_keys


async def test_search_filters_by_type_when_provided():
    app, fake_os = build_search_app(make_os_response([]))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.get("/search?q=fire&type=Anomaly")

    call_args = fake_os.search.call_args
    query_body = call_args.kwargs["body"]
    filters = query_body["query"]["bool"]["filter"]
    filter_terms = {list(f.get("term", {}).keys())[0]: list(f.get("term", {}).values())[0]
                   for f in filters if "term" in f}
    assert filter_terms.get("type") == "Anomaly"


async def test_search_filters_by_tags_when_provided():
    app, fake_os = build_search_app(make_os_response([]))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.get("/search?q=fire&tags=thermal&tags=zone")

    call_args = fake_os.search.call_args
    query_body = call_args.kwargs["body"]
    filters = query_body["query"]["bool"]["filter"]
    terms_filters = [f for f in filters if "terms" in f]
    tag_filter = next((f["terms"]["tags"] for f in terms_filters), None)
    assert set(tag_filter) == {"thermal", "zone"}


async def test_search_paginates_correctly():
    app, fake_os = build_search_app(make_os_response([]))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.get("/search?q=fire&page=2&size=5")

    call_args = fake_os.search.call_args
    query_body = call_args.kwargs["body"]
    assert query_body["from"] == 10
    assert query_body["size"] == 5


async def test_search_returns_422_when_q_missing():
    app, _ = build_search_app(make_os_response([]))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/search")
    assert response.status_code == 422


async def test_suggest_returns_title_list():
    fake_hits = [
        {"page_id": "1", "slug": "fire-anomaly", "type": "Anomaly",
         "status": "Published", "visibility": "Public",
         "title": "Fire Anomaly", "summary": "", "content_text": ""},
        {"page_id": "2", "slug": "fire-trap", "type": "Anomaly",
         "status": "Published", "visibility": "Public",
         "title": "Fire Trap", "summary": "", "content_text": ""},
    ]
    app, fake_os = build_search_app(make_os_response(fake_hits))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/search/suggest?q=fir")
    assert response.status_code == 200
    body = response.json()
    assert "suggestions" in body
    assert "Fire Anomaly" in body["suggestions"]
    assert "Fire Trap" in body["suggestions"]


async def test_suggest_returns_422_when_q_missing():
    app, _ = build_search_app(make_os_response([]))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/search/suggest")
    assert response.status_code == 422


async def test_suggest_applies_public_filter_for_anonymous():
    app, fake_os = build_search_app(make_os_response([]))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.get("/search/suggest?q=fir")

    call_args = fake_os.search.call_args
    query_body = call_args.kwargs["body"]
    filters = query_body["query"]["bool"]["filter"]
    filter_terms = {
        list(f.get("term", {}).keys())[0]: list(f.get("term", {}).values())[0]
        for f in filters if "term" in f
    }
    assert filter_terms.get("visibility") == "Public"
    assert filter_terms.get("status") == "Published"


async def test_suggest_omits_public_filter_for_researcher():
    app, fake_os = build_search_app(make_os_response([]), internal_token="test-token")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.get(
            "/search/suggest?q=fir",
            headers={
                "X-Authenticated-Source": "api-gateway",
                "X-Authenticated-User-Role": "Researcher",
                "X-Internal-Token": "test-token",
            },
        )

    call_args = fake_os.search.call_args
    query_body = call_args.kwargs["body"]
    filters = query_body["query"]["bool"]["filter"]
    filter_keys = [list(f.get("term", {}).keys())[0] for f in filters if "term" in f]
    assert "visibility" not in filter_keys
    assert "status" not in filter_keys


async def test_search_returns_503_when_opensearch_connection_fails():
    app, fake_os = build_search_app(make_os_response([]))
    from opensearchpy import ConnectionError as OSConnectionError
    fake_os.search.side_effect = OSConnectionError("cluster unreachable")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/search?q=fire")
    assert response.status_code == 503
    assert "unavailable" in response.json()["detail"].lower()


async def test_search_returns_502_when_opensearch_transport_error():
    app, fake_os = build_search_app(make_os_response([]))
    from opensearchpy import TransportError
    fake_os.search.side_effect = TransportError(400, "parse_exception", {})
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/search?q=fire")
    assert response.status_code == 502
    assert "error" in response.json()["detail"].lower()


async def test_suggest_returns_503_when_opensearch_connection_fails():
    app, fake_os = build_search_app(make_os_response([]))
    from opensearchpy import ConnectionError as OSConnectionError
    fake_os.search.side_effect = OSConnectionError("cluster unreachable")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/search/suggest?q=fir")
    assert response.status_code == 503


async def test_suggest_returns_502_when_opensearch_transport_error():
    app, fake_os = build_search_app(make_os_response([]))
    from opensearchpy import TransportError
    fake_os.search.side_effect = TransportError(400, "parse_exception", {})
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/search/suggest?q=fir")
    assert response.status_code == 502


async def test_search_returns_500_when_document_missing_required_field():
    """A document without page_id/slug/etc. must return 500, not a stack trace."""
    malformed_os_response = {
        "hits": {
            "total": {"value": 1},
            "hits": [
                {
                    "_id": "bad-doc-1",
                    "_source": {"title": "Fire Anomaly"},  # missing page_id, slug, type, etc.
                    "highlight": {},
                }
            ],
        }
    }
    app, _ = build_search_app(malformed_os_response)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/search?q=fire")
    assert response.status_code == 500
    assert "malformed" in response.json()["detail"].lower()


async def test_suggest_returns_500_when_document_missing_title_field():
    """A suggest document without title must return 500, not a stack trace."""
    malformed_os_response = {
        "hits": {
            "total": {"value": 1},
            "hits": [
                {
                    "_id": "bad-doc-2",
                    "_source": {},  # missing title
                    "highlight": {},
                }
            ],
        }
    }
    app, _ = build_search_app(malformed_os_response)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/search/suggest?q=fir")
    assert response.status_code == 500
    assert "malformed" in response.json()["detail"].lower()


async def test_search_returns_422_when_q_is_empty_string():
    app, _ = build_search_app(make_os_response([]))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/search?q=")
    assert response.status_code == 422


async def test_suggest_returns_422_when_q_is_empty_string():
    app, _ = build_search_app(make_os_response([]))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/search/suggest?q=")
    assert response.status_code == 422


async def test_suggest_query_includes_aliases_field():
    """Suggest must search aliases as well as title so alias-matched pages appear."""
    app, fake_os = build_search_app(make_os_response([]))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.get("/search/suggest?q=bloodsucker")

    call_args = fake_os.search.call_args
    query_body = call_args.kwargs["body"]
    must_clause = query_body["query"]["bool"]["must"][0]
    assert "multi_match" in must_clause, "suggest must use multi_match, not single-field match"
    fields = must_clause["multi_match"]["fields"]
    assert any("aliases" in f for f in fields), "aliases must be included in suggest fields"


async def test_search_falls_back_to_summary_snippet_when_content_text_absent():
    """Snippet should use summary highlight when content_text highlight is absent."""
    os_response = {
        "hits": {
            "total": {"value": 1},
            "hits": [
                {
                    "_source": SAMPLE_HIT,
                    "highlight": {"summary": ["A burning anomaly..."]},
                }
            ],
        }
    }
    app, _ = build_search_app(os_response)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/search?q=fire")
    assert response.status_code == 200
    assert response.json()["hits"][0]["snippet"] == "A burning anomaly..."


async def test_search_falls_back_to_title_snippet_when_content_text_and_summary_absent():
    """Snippet should use title highlight when both content_text and summary are absent."""
    os_response = {
        "hits": {
            "total": {"value": 1},
            "hits": [
                {
                    "_source": SAMPLE_HIT,
                    "highlight": {"title": ["<em>Fire</em> Anomaly"]},
                }
            ],
        }
    }
    app, _ = build_search_app(os_response)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/search?q=fire")
    assert response.status_code == 200
    assert response.json()["hits"][0]["snippet"] == "<em>Fire</em> Anomaly"


async def test_search_returns_empty_snippet_when_no_highlights():
    """Snippet should be empty string when no highlights are returned."""
    os_response = {
        "hits": {
            "total": {"value": 1},
            "hits": [{"_source": SAMPLE_HIT, "highlight": {}}],
        }
    }
    app, _ = build_search_app(os_response)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/search?q=fire")
    assert response.status_code == 200
    assert response.json()["hits"][0]["snippet"] == ""


async def test_internal_request_rejected_when_internal_token_is_whitespace():
    app, fake_os = build_search_app(make_os_response([]), internal_token="   ")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.get(
            "/search?q=fire",
            headers={
                "X-Authenticated-Source": "api-gateway",
                "X-Authenticated-User-Role": "Researcher",
                "X-Internal-Token": "   ",
            },
        )

    filters = fake_os.search.call_args.kwargs["body"]["query"]["bool"]["filter"]
    filter_keys = [list(f.get("term", {}).keys())[0] for f in filters if "term" in f]
    assert "visibility" in filter_keys
    assert "status" in filter_keys


async def test_search_applies_visibility_filter_for_internal_request_when_provided():
    """Internal users can narrow by visibility when explicitly passed."""
    app, fake_os = build_search_app(make_os_response([]), internal_token="test-token")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.get(
            "/search?q=fire&visibility=Private",
            headers={
                "X-Authenticated-Source": "api-gateway",
                "X-Authenticated-User-Role": "Researcher",
                "X-Internal-Token": "test-token",
            },
        )

    call_args = fake_os.search.call_args
    filters = call_args.kwargs["body"]["query"]["bool"]["filter"]
    filter_terms = {
        list(f["term"].keys())[0]: list(f["term"].values())[0]
        for f in filters if "term" in f
    }
    assert filter_terms.get("visibility") == "Private"


async def test_search_applies_status_filter_for_internal_request_when_provided():
    """Internal users can narrow by status when explicitly passed."""
    app, fake_os = build_search_app(make_os_response([]), internal_token="test-token")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.get(
            "/search?q=fire&status=Draft",
            headers={
                "X-Authenticated-Source": "api-gateway",
                "X-Authenticated-User-Role": "Researcher",
                "X-Internal-Token": "test-token",
            },
        )

    call_args = fake_os.search.call_args
    filters = call_args.kwargs["body"]["query"]["bool"]["filter"]
    filter_terms = {
        list(f["term"].keys())[0]: list(f["term"].values())[0]
        for f in filters if "term" in f
    }
    assert filter_terms.get("status") == "Draft"


async def test_search_treats_as_public_when_internal_token_mismatch():
    """Headers with wrong token must be treated as a public (not internal) request."""
    app, fake_os = build_search_app(make_os_response([]), internal_token="secret-abc")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.get(
            "/search?q=fire",
            headers={
                "X-Authenticated-Source": "api-gateway",
                "X-Authenticated-User-Role": "Researcher",
                "X-Internal-Token": "WRONG_TOKEN",
            },
        )

    call_args = fake_os.search.call_args
    filters = call_args.kwargs["body"]["query"]["bool"]["filter"]
    filter_terms = {
        list(f.get("term", {}).keys())[0]: list(f.get("term", {}).values())[0]
        for f in filters if "term" in f
    }
    assert filter_terms.get("visibility") == "Public"
    assert filter_terms.get("status") == "Published"


async def test_internal_request_rejected_when_internal_token_not_configured():
    # internal_token="" (default) — no request may claim internal status
    app, fake_os = build_search_app(make_os_response([]))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.get(
            "/search?q=fire",
            headers={
                "X-Authenticated-Source": "api-gateway",
                "X-Authenticated-User-Role": "Researcher",
            },
        )

    filters = fake_os.search.call_args.kwargs["body"]["query"]["bool"]["filter"]
    filter_keys = [list(f.get("term", {}).keys())[0] for f in filters if "term" in f]
    assert "visibility" in filter_keys
    assert "status" in filter_keys


async def test_internal_request_rejected_when_token_mismatch():
    app, fake_os = build_search_app(make_os_response([]), internal_token="secret")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.get(
            "/search?q=fire",
            headers={
                "X-Authenticated-Source": "api-gateway",
                "X-Authenticated-User-Role": "Researcher",
                "X-Internal-Token": "wrong-secret",
            },
        )

    filters = fake_os.search.call_args.kwargs["body"]["query"]["bool"]["filter"]
    filter_keys = [list(f.get("term", {}).keys())[0] for f in filters if "term" in f]
    assert "visibility" in filter_keys
    assert "status" in filter_keys


async def test_search_treats_as_internal_when_token_matches():
    """Headers with correct token must be treated as an internal request."""
    app, fake_os = build_search_app(make_os_response([]), internal_token="secret-abc")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.get(
            "/search?q=fire",
            headers={
                "X-Authenticated-Source": "api-gateway",
                "X-Authenticated-User-Role": "Researcher",
                "X-Internal-Token": "secret-abc",
            },
        )

    call_args = fake_os.search.call_args
    filters = call_args.kwargs["body"]["query"]["bool"]["filter"]
    filter_keys = [list(f.get("term", {}).keys())[0] for f in filters if "term" in f]
    assert "visibility" not in filter_keys
    assert "status" not in filter_keys
