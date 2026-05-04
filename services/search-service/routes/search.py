import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from opensearchpy import AsyncOpenSearch
from opensearchpy import ConnectionError as OSConnectionError, TransportError

from config import Settings, get_settings
from opensearch import get_opensearch_client
from schemas import SearchHit, SearchResponse, SuggestResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["search"])

_INTERNAL_ROLES = {"researcher", "editor", "admin"}


def _is_internal_request(request: Request, settings: Settings) -> bool:
    source = request.headers.get("x-authenticated-source", "")
    role = request.headers.get("x-authenticated-user-role", "")
    token = request.headers.get("x-internal-token", "")
    if source != "api-gateway":
        return False
    if role.lower() not in _INTERNAL_ROLES:
        return False
    if settings.internal_token and token != settings.internal_token:
        return False
    return True


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
    q: Annotated[str, Query(min_length=1, max_length=500)],
    type: Annotated[str | None, Query()] = None,
    visibility: Annotated[str | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    tags: Annotated[list[str] | None, Query()] = None,
    page: Annotated[int, Query(ge=0)] = 0,
    size: Annotated[int, Query(ge=1, le=50)] = 10,
    settings: Settings = Depends(get_settings),
    os_client: AsyncOpenSearch = Depends(get_opensearch_client),
) -> SearchResponse:
    internal = _is_internal_request(request, settings)
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
    try:
        result = await os_client.search(index=settings.opensearch_index, body=body)
    except OSConnectionError as exc:
        logger.error("OpenSearch unreachable during search: %r", exc)
        raise HTTPException(status_code=503, detail="Search index is currently unavailable.")
    except TransportError as exc:
        logger.error("OpenSearch transport error during search: status=%s info=%s", exc.status_code, exc.info)
        raise HTTPException(status_code=502, detail="Search index returned an error.")

    try:
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
    except (KeyError, ValueError) as exc:
        logger.error("Malformed OpenSearch document missing field %s", exc)
        raise HTTPException(status_code=500, detail="Search index returned a malformed document.")

    return SearchResponse(total=total, hits=hits)


@router.get("/search/suggest", response_model=SuggestResponse)
async def suggest(
    request: Request,
    q: Annotated[str, Query(min_length=1, max_length=500)],
    type: Annotated[str | None, Query()] = None,
    settings: Settings = Depends(get_settings),
    os_client: AsyncOpenSearch = Depends(get_opensearch_client),
) -> SuggestResponse:
    internal = _is_internal_request(request, settings)
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
                "must": [
                    {
                        "multi_match": {
                            "query": q,
                            "fields": ["title", "aliases"],
                            "type": "phrase_prefix",
                        }
                    }
                ],
                "filter": filters,
            }
        },
        "_source": ["title"],
    }
    try:
        result = await os_client.search(index=settings.opensearch_index, body=body)
    except OSConnectionError as exc:
        logger.error("OpenSearch unreachable during suggest: %r", exc)
        raise HTTPException(status_code=503, detail="Search index is currently unavailable.")
    except TransportError as exc:
        logger.error("OpenSearch transport error during suggest: status=%s info=%s", exc.status_code, exc.info)
        raise HTTPException(status_code=502, detail="Search index returned an error.")

    try:
        titles = [h["_source"]["title"] for h in result["hits"]["hits"]]
    except (KeyError, ValueError) as exc:
        logger.error("Malformed OpenSearch document missing field %s in suggest", exc)
        raise HTTPException(status_code=500, detail="Search index returned a malformed document.")

    return SuggestResponse(suggestions=titles)
