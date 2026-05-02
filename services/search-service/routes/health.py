from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from opensearch import get_opensearch_client

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readiness")
async def readiness(
    os_client=Depends(get_opensearch_client),
) -> JSONResponse:
    try:
        alive = await os_client.ping()
    except Exception:
        alive = False

    if not alive:
        return JSONResponse(status_code=503, content={"status": "unavailable"})
    return JSONResponse(content={"status": "ready"})
