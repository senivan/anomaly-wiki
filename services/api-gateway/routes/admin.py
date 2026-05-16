from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from clients.http import forward_authenticated_request
from config import Settings, get_settings
from security import AuthContext, require_role

router = APIRouter(prefix="/admin", tags=["admin"])


async def _forward_admin_request(
    request: Request,
    *,
    auth: AuthContext,
    upstream_path: str,
    settings: Settings,
) -> Response:
    return await forward_authenticated_request(
        request,
        auth=auth,
        service="researcher-auth-service",
        upstream_base_url=settings.researcher_auth_base_url,
        upstream_path=upstream_path,
        settings=settings,
    )


@router.get("/users")
async def proxy_list_users(
    request: Request,
    auth: AuthContext = Depends(require_role("Admin")),
    settings: Settings = Depends(get_settings),
) -> Response:
    return await _forward_admin_request(
        request,
        auth=auth,
        upstream_path="/admin/users",
        settings=settings,
    )


@router.patch("/users/{user_id}/role")
async def proxy_update_user_role(
    user_id: UUID,
    request: Request,
    auth: AuthContext = Depends(require_role("Admin")),
    settings: Settings = Depends(get_settings),
) -> Response:
    return await _forward_admin_request(
        request,
        auth=auth,
        upstream_path=f"/admin/users/{user_id}/role",
        settings=settings,
    )
