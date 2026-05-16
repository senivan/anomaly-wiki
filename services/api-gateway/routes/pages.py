import json
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from clients.http import PROTECTED_FORWARD_STRIP_HEADERS, forward_authenticated_request, forward_request
from config import Settings, get_settings
from errors import GatewayAuthError
from security import AuthContext, get_auth_context

router = APIRouter(prefix="/pages", tags=["pages"])


async def _forward_protected_page_request(
    request: Request,
    *,
    auth: AuthContext,
    upstream_path: str,
    settings: Settings,
) -> Response:
    return await forward_authenticated_request(
        request,
        auth=auth,
        service="encyclopedia-service",
        upstream_base_url=settings.encyclopedia_base_url,
        upstream_path=upstream_path,
        settings=settings,
    )


async def _optional_auth(request: Request, settings: Settings) -> AuthContext | None:
    if not request.headers.get("Authorization"):
        return None
    return await get_auth_context(request, settings)


def _assert_public_page_read(response: Response) -> None:
    payload = json.loads(response.body)
    page = payload.get("page") if isinstance(payload, dict) else None
    if not isinstance(page, dict):
        raise GatewayAuthError(
            status_code=404,
            code="page_not_public",
            message="Page not found or access denied.",
        )
    if page.get("status") != "Published" or page.get("visibility") != "Public":
        raise GatewayAuthError(
            status_code=404,
            code="page_not_public",
            message="Page not found or access denied.",
        )


@router.get("/mine")
async def proxy_list_my_pages(
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
    settings: Settings = Depends(get_settings),
) -> Response:
    return await _forward_protected_page_request(
        request,
        auth=auth,
        upstream_path="/pages/mine",
        settings=settings,
    )


@router.get("/{page_id}")
async def proxy_get_page_state(
    page_id: UUID,
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
    settings: Settings = Depends(get_settings),
) -> Response:
    return await _forward_protected_page_request(
        request,
        auth=auth,
        upstream_path=f"/pages/{page_id}",
        settings=settings,
    )


@router.get("/{page_id}/revisions")
async def proxy_list_page_revisions(
    page_id: UUID,
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
    settings: Settings = Depends(get_settings),
) -> Response:
    return await _forward_protected_page_request(
        request,
        auth=auth,
        upstream_path=f"/pages/{page_id}/revisions",
        settings=settings,
    )


@router.get("/{page_id}/revisions/{revision_id}")
async def proxy_get_page_revision(
    page_id: UUID,
    revision_id: UUID,
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
    settings: Settings = Depends(get_settings),
) -> Response:
    return await _forward_protected_page_request(
        request,
        auth=auth,
        upstream_path=f"/pages/{page_id}/revisions/{revision_id}",
        settings=settings,
    )


@router.get("/slug/{slug}")
async def proxy_get_page_state_by_slug(
    slug: str,
    request: Request,
    settings: Settings = Depends(get_settings),
) -> Response:
    auth = await _optional_auth(request, settings)
    if auth is not None:
        return await _forward_protected_page_request(
            request,
            auth=auth,
            upstream_path=f"/pages/slug/{slug}",
            settings=settings,
        )

    response = await forward_request(
        request,
        service="encyclopedia-service",
        upstream_base_url=settings.encyclopedia_base_url,
        upstream_path=f"/pages/slug/{slug}",
        settings=settings,
        excluded_headers=PROTECTED_FORWARD_STRIP_HEADERS,
    )
    _assert_public_page_read(response)
    return response


@router.post("")
async def proxy_create_page(
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
    settings: Settings = Depends(get_settings),
) -> Response:
    return await _forward_protected_page_request(
        request,
        auth=auth,
        upstream_path="/pages",
        settings=settings,
    )


@router.post("/{page_id}/drafts")
async def proxy_create_draft_revision(
    page_id: UUID,
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
    settings: Settings = Depends(get_settings),
) -> Response:
    return await _forward_protected_page_request(
        request,
        auth=auth,
        upstream_path=f"/pages/{page_id}/drafts",
        settings=settings,
    )


@router.put("/{page_id}/metadata")
async def proxy_update_page_metadata(
    page_id: UUID,
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
    settings: Settings = Depends(get_settings),
) -> Response:
    return await _forward_protected_page_request(
        request,
        auth=auth,
        upstream_path=f"/pages/{page_id}/metadata",
        settings=settings,
    )


@router.post("/{page_id}/publish")
async def proxy_publish_revision(
    page_id: UUID,
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
    settings: Settings = Depends(get_settings),
) -> Response:
    return await _forward_protected_page_request(
        request,
        auth=auth,
        upstream_path=f"/pages/{page_id}/publish",
        settings=settings,
    )


@router.post("/{page_id}/revert")
async def proxy_revert_revision(
    page_id: UUID,
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
    settings: Settings = Depends(get_settings),
) -> Response:
    return await _forward_protected_page_request(
        request,
        auth=auth,
        upstream_path=f"/pages/{page_id}/revert",
        settings=settings,
    )


@router.post("/{page_id}/status")
async def proxy_transition_page_status(
    page_id: UUID,
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
    settings: Settings = Depends(get_settings),
) -> Response:
    return await _forward_protected_page_request(
        request,
        auth=auth,
        upstream_path=f"/pages/{page_id}/status",
        settings=settings,
    )
