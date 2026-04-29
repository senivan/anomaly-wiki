from fastapi import APIRouter, Depends

from config import Settings, get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def readiness(settings: Settings = Depends(get_settings)) -> dict[str, object]:
    return {
        "status": "ok",
        "services": {
            "researcher_auth_service": str(settings.researcher_auth_base_url),
            "encyclopedia_service": str(settings.encyclopedia_base_url),
            "media_service": str(settings.media_service_base_url),
            "search_service": str(settings.search_service_base_url),
        },
    }
