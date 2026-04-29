from fastapi import APIRouter, Depends, HTTPException

from config import Settings, get_settings
from db import check_database_connection

router = APIRouter(tags=["health"])


@router.get("/health")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def readiness(settings: Settings = Depends(get_settings)) -> dict[str, object]:
    try:
        await check_database_connection()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "error",
                "services": {"database": "unavailable"},
                "database_url": settings.database_url,
            },
        ) from exc

    return {
        "status": "ok",
        "services": {"database": "ok"},
        "database_url": settings.database_url,
    }
