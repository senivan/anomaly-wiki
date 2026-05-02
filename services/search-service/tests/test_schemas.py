from schemas import SearchQuery, SearchHit, SearchResponse, SuggestResponse


def test_search_query_defaults():
    q = SearchQuery(q="anomaly")
    assert q.page == 0
    assert q.size == 10
    assert q.type is None
    assert q.visibility is None
    assert q.status is None
    assert q.tags is None


def test_search_query_size_clamped():
    q = SearchQuery(q="x", size=200)
    assert q.size == 50


def test_search_hit_fields():
    hit = SearchHit(
        page_id="some-uuid",
        slug="fire-anomaly",
        type="Anomaly",
        title="Fire Anomaly",
        summary="A burning anomaly",
        snippet="...burning anomaly found near...",
        status="Published",
        visibility="Public",
    )
    assert hit.slug == "fire-anomaly"


def test_search_response_structure():
    resp = SearchResponse(total=1, hits=[])
    assert resp.total == 1


def test_suggest_response_structure():
    resp = SuggestResponse(suggestions=["Fire Anomaly", "Fire Trap"])
    assert len(resp.suggestions) == 2
