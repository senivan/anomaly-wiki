from __future__ import annotations

import logging
from hashlib import sha256
from pathlib import PurePath
from urllib.parse import urlparse, urlunparse
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from config import Settings, get_settings
from db import get_async_session
from repository import MediaAssetRepository
from schemas import MediaAssetResponse, SignedDownloadUrlResponse
from storage import ObjectStorage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/media", tags=["media"])

_GATEWAY_SOURCE = "api-gateway"
_MAX_FILENAME_LEN = 255
_MAX_STORAGE_PATH_LEN = 1024


def _safe_filename(filename: str | None) -> str:
    if not filename:
        return "upload.bin"
    name = PurePath(filename).name.strip()
    return name or "upload.bin"


def _rewrite_url_for_public_access(url: str, public_base_url: str) -> str:
    """Replace the scheme+host of a presigned URL with the public base URL."""
    parsed = urlparse(url)
    public_parsed = urlparse(public_base_url)
    rewritten = parsed._replace(scheme=public_parsed.scheme, netloc=public_parsed.netloc)
    return urlunparse(rewritten)


async def get_storage(request: Request) -> ObjectStorage:
    return request.app.state.storage_backend


def verify_gateway_source(
    authenticated_source: str | None = Header(default=None, alias="X-Authenticated-Source"),
) -> None:
    """Reject requests that did not originate from api-gateway."""
    if authenticated_source != _GATEWAY_SOURCE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requests must originate from api-gateway.",
        )


@router.post(
    "",
    response_model=MediaAssetResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_gateway_source)],
)
async def upload_media(
    file: UploadFile,
    request: Request,
    uploaded_by_header: str | None = Header(default=None, alias="X-Authenticated-User-Id"),
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_async_session),
    storage_backend: ObjectStorage = Depends(get_storage),
) -> MediaAssetResponse:
    if uploaded_by_header is None:
        raise HTTPException(status_code=401, detail="Authenticated user id is required.")
    try:
        uploaded_by = UUID(uploaded_by_header)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Authenticated user id must be a UUID.") from exc

    data = await file.read(settings.max_upload_bytes + 1)
    # NOTE: The entire file is buffered in memory (up to max_upload_bytes + 1
    # bytes) before being written to object storage. This is adequate for the
    # configured default limit (50 MB) but would need to become a streaming
    # read-and-hash pipeline if the limit is raised significantly or concurrent
    # upload volume is high.
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file must not be empty.")
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Upload exceeds the maximum allowed size of {settings.max_upload_bytes} bytes.",
        )

    asset_id = uuid4()
    filename = _safe_filename(file.filename)
    mime_type = file.content_type or "application/octet-stream"
    storage_path = f"assets/{asset_id}/{filename}"
    checksum = sha256(data).hexdigest()

    if len(filename) > _MAX_FILENAME_LEN:
        raise HTTPException(
            status_code=400,
            detail=f"Filename exceeds the maximum allowed length of {_MAX_FILENAME_LEN} characters.",
        )
    if len(storage_path) > _MAX_STORAGE_PATH_LEN:
        raise HTTPException(
            status_code=400,
            detail=f"Derived storage path exceeds the maximum allowed length of {_MAX_STORAGE_PATH_LEN} characters.",
        )

    await storage_backend.put_object(
        storage_path=storage_path,
        data=data,
        content_type=mime_type,
    )
    # NOTE: put_object is not idempotent with respect to asset_id. If a client
    # retries after a timeout the object is overwritten (safe), but a fresh
    # DB insert for the same asset_id will fail on the unique constraint.
    # Callers are expected to generate a new asset_id on each retry attempt.

    repository = MediaAssetRepository(session)
    try:
        asset = await repository.create_asset(
            asset_id=asset_id,
            filename=filename,
            mime_type=mime_type,
            size_bytes=len(data),
            storage_path=storage_path,
            uploaded_by=uploaded_by,
            checksum_sha256=checksum,
        )
        await session.commit()
        await session.refresh(asset)
    except Exception:
        await session.rollback()
        try:
            await storage_backend.delete_object(storage_path=storage_path)
        except Exception:
            logger.exception("Failed to clean up orphaned object %s after DB error", storage_path)
            # The blob will remain unreferenced in object storage. A periodic
            # garbage-collection job or manual cleanup is needed to recover it.
        raise

    return MediaAssetResponse.model_validate(asset)


@router.get(
    "/{asset_id}",
    response_model=MediaAssetResponse,
    dependencies=[Depends(verify_gateway_source)],
)
async def get_media_asset(
    asset_id: UUID,
    session: AsyncSession = Depends(get_async_session),
) -> MediaAssetResponse:
    repository = MediaAssetRepository(session)
    asset = await repository.get_asset(asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail=f"Media asset {asset_id} was not found.")
    return MediaAssetResponse.model_validate(asset)


@router.get(
    "/{asset_id}/download-url",
    response_model=SignedDownloadUrlResponse,
    dependencies=[Depends(verify_gateway_source)],
)
async def get_media_download_url(
    asset_id: UUID,
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_async_session),
    storage_backend: ObjectStorage = Depends(get_storage),
) -> SignedDownloadUrlResponse:
    repository = MediaAssetRepository(session)
    asset = await repository.get_asset(asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail=f"Media asset {asset_id} was not found.")

    url = await storage_backend.presigned_get_url(
        storage_path=asset.storage_path,
        expires_in_seconds=settings.signed_url_ttl_seconds,
    )

    if settings.public_storage_base_url:
        # Rewrites the internal storage hostname (e.g. minio:9000) to the
        # externally-reachable base URL. The public endpoint must serve the
        # same bucket namespace and path structure as the internal MinIO
        # endpoint (e.g. a reverse proxy or MinIO exposed on a public port).
        url = _rewrite_url_for_public_access(url, settings.public_storage_base_url)

    return SignedDownloadUrlResponse(
        asset_id=asset.id,
        url=url,
        expires_in_seconds=settings.signed_url_ttl_seconds,
    )
