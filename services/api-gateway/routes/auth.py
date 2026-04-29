from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from clients.http import forward_request
from config import Settings, get_settings

router = APIRouter(prefix="/auth", tags=["auth"])


async def _proxy_auth_request(
    request: Request,
    settings: Settings,
    upstream_path: str,
) -> Response:
    return await forward_request(
        request,
        service="researcher-auth-service",
        upstream_base_url=settings.researcher_auth_base_url,
        upstream_path=upstream_path,
        settings=settings,
    )


@router.post("/register")
async def proxy_register(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> Response:
    return await _proxy_auth_request(request, settings, "/auth/register")


@router.post("/login")
async def proxy_login(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> Response:
    return await _proxy_auth_request(request, settings, "/auth/login")


@router.post("/logout")
async def proxy_logout(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> Response:
    return await _proxy_auth_request(request, settings, "/auth/logout")


@router.get("/jwks")
async def proxy_jwks(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> Response:
    return await _proxy_auth_request(request, settings, "/auth/jwks")
