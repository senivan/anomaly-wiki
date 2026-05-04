from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from clients.http import forward_authenticated_request
from config import Settings, get_settings
from security import AuthContext, get_auth_context

router = APIRouter(prefix="/media", tags=["media"])


async def _proxy_media_request(
    request: Request,
    auth: AuthContext,
    settings: Settings,
    upstream_path: str,
) -> Response:
    return await forward_authenticated_request(
        request,
        auth=auth,
        service="media-service",
        upstream_base_url=settings.media_service_base_url,
        upstream_path=upstream_path,
        settings=settings,
    )


@router.post("")
async def proxy_upload_media(
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
    settings: Settings = Depends(get_settings),
) -> Response:
    return await _proxy_media_request(request, auth, settings, "/media")


@router.get("/{asset_id}")
async def proxy_get_media_asset(
    asset_id: UUID,
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
    settings: Settings = Depends(get_settings),
) -> Response:
    return await _proxy_media_request(request, auth, settings, f"/media/{asset_id}")


@router.get("/{asset_id}/download-url")
async def proxy_get_media_download_url(
    asset_id: UUID,
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
    settings: Settings = Depends(get_settings),
) -> Response:
    return await _proxy_media_request(
        request,
        auth,
        settings,
        f"/media/{asset_id}/download-url",
    )
