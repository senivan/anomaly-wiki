from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from db import check_database_connection

router = APIRouter(tags=["health"])


@router.get("/health")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def readiness(request: Request) -> JSONResponse:
    services: dict[str, dict[str, str]] = {}

    try:
        await check_database_connection()
        services["database"] = {"status": "ok"}
    except Exception as exc:
        services["database"] = {
            "status": "error",
            "detail": str(exc) or exc.__class__.__name__,
        }

    try:
        await request.app.state.storage_backend.check_connection()
        services["object_storage"] = {"status": "ok"}
    except Exception as exc:
        services["object_storage"] = {
            "status": "error",
            "detail": str(exc) or exc.__class__.__name__,
        }

    is_ready = all(service["status"] == "ok" for service in services.values())
    return JSONResponse(
        status_code=200 if is_ready else 503,
        content={"status": "ok" if is_ready else "degraded", "services": services},
    )
