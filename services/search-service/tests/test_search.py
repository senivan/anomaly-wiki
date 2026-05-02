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
    app, fake_os = build_search_app(make_os_response([]))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.get(
            "/search?q=fire",
            headers={
                "X-Authenticated-Source": "api-gateway",
                "X-Authenticated-User-Role": "Researcher",
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
    app, fake_os = build_search_app(make_os_response([]))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.get(
            "/search/suggest?q=fir",
            headers={
                "X-Authenticated-Source": "api-gateway",
                "X-Authenticated-User-Role": "Researcher",
            },
        )

    call_args = fake_os.search.call_args
    query_body = call_args.kwargs["body"]
    filters = query_body["query"]["bool"]["filter"]
    filter_keys = [list(f.get("term", {}).keys())[0] for f in filters if "term" in f]
    assert "visibility" not in filter_keys
    assert "status" not in filter_keys
