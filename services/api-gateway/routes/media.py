from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from clients.http import forward_authenticated_request
from config import Settings, get_settings
from errors import GatewayAuthError
from security import AuthContext, get_auth_context

router = APIRouter(prefix="/media", tags=["media"])


def _validate_media_upload_request(request: Request, settings: Settings) -> None:
    content_type = request.headers.get("content-type", "")
    media_type = content_type.split(";", 1)[0].strip().lower()
    if media_type != "multipart/form-data":
        raise GatewayAuthError(
            status_code=415,
            code="unsupported_media_upload_content_type",
            message="Media uploads must use multipart/form-data.",
            details={"content_type": content_type or None},
        )

    content_length = request.headers.get("content-length")
    if content_length is None:
        raise GatewayAuthError(
            status_code=411,
            code="missing_content_length",
            message="Media uploads must include a Content-Length header.",
        )

    try:
        upload_size = int(content_length)
    except ValueError as exc:
        raise GatewayAuthError(
            status_code=400,
            code="invalid_content_length",
            message="Content-Length must be an integer.",
            details={"content_length": content_length},
        ) from exc

    if upload_size < 0:
        raise GatewayAuthError(
            status_code=400,
            code="invalid_content_length",
            message="Content-Length must be zero or greater.",
            details={"content_length": content_length},
        )

    if upload_size > settings.media_upload_max_bytes:
        raise GatewayAuthError(
            status_code=413,
            code="media_upload_too_large",
            message="Media upload exceeds the configured gateway limit.",
            details={
                "max_bytes": settings.media_upload_max_bytes,
                "content_length": upload_size,
            },
        )


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
    _validate_media_upload_request(request, settings)
    return await _proxy_media_request(request, auth, settings, "/media")


@router.get("")
async def proxy_list_media_assets(
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
    settings: Settings = Depends(get_settings),
) -> Response:
    return await _proxy_media_request(request, auth, settings, "/media")


@router.get("/batch")
async def proxy_get_media_assets_batch(
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
    settings: Settings = Depends(get_settings),
) -> Response:
    return await _proxy_media_request(request, auth, settings, "/media/batch")


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
