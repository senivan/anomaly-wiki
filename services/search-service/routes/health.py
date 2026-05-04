import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from opensearch import get_opensearch_client

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readiness")
async def readiness(
    os_client=Depends(get_opensearch_client),
) -> JSONResponse:
    try:
        alive = await os_client.ping()
    except Exception as exc:
        logger.error("OpenSearch ping failed: %s: %s", type(exc).__name__, exc)
        alive = False

    if not alive:
        return JSONResponse(status_code=503, content={"status": "unavailable"})
    return JSONResponse(content={"status": "ready"})
