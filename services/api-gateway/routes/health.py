from collections.abc import Iterable

import asyncio

import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from config import Settings, get_settings
from errors import REQUEST_ID_HEADER

router = APIRouter(tags=["health"])


def _service_targets(settings: Settings) -> Iterable[tuple[str, str]]:
    return (
        ("researcher_auth_service", str(settings.researcher_auth_base_url)),
        ("encyclopedia_service", str(settings.encyclopedia_base_url)),
        ("media_service", str(settings.media_service_base_url)),
        ("search_service", str(settings.search_service_base_url)),
    )


async def _probe_service_health(
    client: httpx.AsyncClient,
    *,
    service: str,
    base_url: str,
) -> tuple[str, dict[str, object]]:
    try:
        response = await client.get(f"{base_url.rstrip('/')}/health")
    except httpx.HTTPError as exc:
        return service, {
            "status": "error",
            "url": base_url,
            "detail": str(exc) or exc.__class__.__name__,
        }

    service_status = "ok" if response.is_success else "error"
    payload: dict[str, object] = {
        "status": service_status,
        "url": base_url,
        "status_code": response.status_code,
    }
    return service, payload


@router.get("/health")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def readiness(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> JSONResponse:
    transport = getattr(request.app.state, "upstream_transport", None)
    headers = {}
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        headers[REQUEST_ID_HEADER] = request_id

    async with httpx.AsyncClient(
        timeout=settings.upstream_timeout_seconds,
        transport=transport,
        headers=headers,
        follow_redirects=False,
    ) as client:
        checks = await asyncio.gather(
            *[
                _probe_service_health(client, service=service, base_url=base_url)
                for service, base_url in _service_targets(settings)
            ]
        )

    services = dict(checks)
    is_ready = all(service["status"] == "ok" for service in services.values())
    return JSONResponse(
        status_code=200 if is_ready else 503,
        content={
            "status": "ok" if is_ready else "degraded",
            "services": services,
        },
    )
