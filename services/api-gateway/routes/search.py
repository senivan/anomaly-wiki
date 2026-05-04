from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from clients.http import (
    PROTECTED_FORWARD_STRIP_HEADERS,
    build_authenticated_forward_headers,
    forward_request,
)
from config import Settings, get_settings
from security import AuthContext, get_auth_context

router = APIRouter(tags=["search"])


async def _optional_auth(request: Request, settings: Settings) -> AuthContext | None:
    if not request.headers.get("Authorization"):
        return None
    return await get_auth_context(request, settings)


async def _forward_search(
    request: Request,
    upstream_path: str,
    settings: Settings,
) -> Response:
    auth = await _optional_auth(request, settings)
    forwarded_headers: dict[str, str] | None = None
    if auth:
        forwarded_headers = build_authenticated_forward_headers(auth)
        if settings.search_internal_token:
            forwarded_headers["X-Internal-Token"] = settings.search_internal_token
    return await forward_request(
        request,
        service="search-service",
        upstream_base_url=settings.search_service_base_url,
        upstream_path=upstream_path,
        settings=settings,
        forwarded_headers=forwarded_headers,
        excluded_headers=PROTECTED_FORWARD_STRIP_HEADERS,
    )


@router.get("/search")
async def proxy_search(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> Response:
    return await _forward_search(request, "/search", settings)


@router.get("/search/suggest")
async def proxy_suggest(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> Response:
    return await _forward_search(request, "/search/suggest", settings)
