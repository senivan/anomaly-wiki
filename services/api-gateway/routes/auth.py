from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from clients.http import forward_request
from config import Settings, get_settings
from errors import GatewayUpstreamResponseError

router = APIRouter(prefix="/auth", tags=["auth"])


async def _proxy_auth_request(
    request: Request,
    settings: Settings,
    upstream_path: str,
) -> Response:
    try:
        return await forward_request(
            request,
            service="researcher-auth-service",
            upstream_base_url=settings.researcher_auth_base_url,
            upstream_path=upstream_path,
            settings=settings,
        )
    except GatewayUpstreamResponseError as exc:
        if (
            upstream_path == "/auth/login"
            and exc.status_code == 400
            and isinstance(exc.body, dict)
            and exc.body.get("detail") == "LOGIN_BAD_CREDENTIALS"
        ):
            raise GatewayUpstreamResponseError(
                service=exc.service,
                status_code=401,
                body=exc.body,
                headers=exc.headers,
            ) from exc
        raise


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
