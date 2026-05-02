from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from opensearchpy import AsyncOpenSearch

from config import Settings, get_settings
from opensearch import get_opensearch_client
from schemas import SearchHit, SearchResponse, SuggestResponse

router = APIRouter(tags=["search"])

_INTERNAL_ROLES = {"researcher", "editor", "admin"}


def _is_internal_request(request: Request) -> bool:
    source = request.headers.get("x-authenticated-source", "")
    role = request.headers.get("x-authenticated-user-role", "")
    return source == "api-gateway" and role.lower() in _INTERNAL_ROLES


def _build_search_body(
    *,
    q: str,
    page: int,
    size: int,
    type_: str | None,
    visibility: str | None,
    status: str | None,
    tags: list[str] | None,
    internal: bool,
) -> dict:
    must = [
        {
            "multi_match": {
                "query": q,
                "fields": ["title^3", "summary^2", "content_text", "aliases^2"],
                "type": "best_fields",
                "fuzziness": "AUTO",
            }
        }
    ]
    filters: list[dict] = []

    if not internal:
        filters.append({"term": {"visibility": "Public"}})
        filters.append({"term": {"status": "Published"}})
    else:
        if visibility:
            filters.append({"term": {"visibility": visibility}})
        if status:
            filters.append({"term": {"status": status}})

    if type_:
        filters.append({"term": {"type": type_}})
    if tags:
        filters.append({"terms": {"tags": tags}})

    return {
        "from": page * size,
        "size": size,
        "query": {"bool": {"must": must, "filter": filters}},
        "highlight": {
            "fields": {
                "title": {},
                "summary": {},
                "content_text": {"fragment_size": 150, "number_of_fragments": 1},
            }
        },
    }


def _extract_snippet(highlight: dict) -> str:
    for field in ("content_text", "summary", "title"):
        fragments = highlight.get(field, [])
        if fragments:
            return fragments[0]
    return ""


@router.get("/search", response_model=SearchResponse)
async def search(
    request: Request,
    q: str,
    type: Annotated[str | None, Query()] = None,
    visibility: Annotated[str | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    tags: Annotated[list[str] | None, Query()] = None,
    page: Annotated[int, Query(ge=0)] = 0,
    size: Annotated[int, Query(ge=1, le=50)] = 10,
    settings: Settings = Depends(get_settings),
    os_client: AsyncOpenSearch = Depends(get_opensearch_client),
) -> SearchResponse:
    internal = _is_internal_request(request)
    body = _build_search_body(
        q=q,
        page=page,
        size=size,
        type_=type,
        visibility=visibility,
        status=status,
        tags=tags,
        internal=internal,
    )
    result = await os_client.search(index=settings.opensearch_index, body=body)
    total = result["hits"]["total"]["value"]
    hits = []
    for raw in result["hits"]["hits"]:
        src = raw["_source"]
        snippet = _extract_snippet(raw.get("highlight", {}))
        hits.append(
            SearchHit(
                page_id=src["page_id"],
                slug=src["slug"],
                type=src["type"],
                title=src["title"],
                summary=src["summary"],
                snippet=snippet,
                status=src["status"],
                visibility=src["visibility"],
            )
        )
    return SearchResponse(total=total, hits=hits)


@router.get("/search/suggest", response_model=SuggestResponse)
async def suggest(
    request: Request,
    q: str,
    type: Annotated[str | None, Query()] = None,
    settings: Settings = Depends(get_settings),
    os_client: AsyncOpenSearch = Depends(get_opensearch_client),
) -> SuggestResponse:
    internal = _is_internal_request(request)
    filters: list[dict] = []
    if not internal:
        filters.append({"term": {"visibility": "Public"}})
        filters.append({"term": {"status": "Published"}})
    if type:
        filters.append({"term": {"type": type}})

    body = {
        "size": 10,
        "query": {
            "bool": {
                "must": [{"match_phrase_prefix": {"title": {"query": q}}}],
                "filter": filters,
            }
        },
        "_source": ["title"],
    }
    result = await os_client.search(index=settings.opensearch_index, body=body)
    titles = [h["_source"]["title"] for h in result["hits"]["hits"]]
    return SuggestResponse(suggestions=titles)
