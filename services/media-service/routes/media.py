from __future__ import annotations

from hashlib import sha256
from pathlib import PurePath
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from config import Settings, get_settings
from db import get_async_session
from repository import MediaAssetRepository
from schemas import MediaAssetResponse, SignedDownloadUrlResponse
from storage import ObjectStorage

router = APIRouter(prefix="/media", tags=["media"])


def _safe_filename(filename: str | None) -> str:
    if not filename:
        return "upload.bin"
    name = PurePath(filename).name.strip()
    return name or "upload.bin"


async def get_storage(request: Request) -> ObjectStorage:
    return request.app.state.storage_backend


@router.post("", response_model=MediaAssetResponse, status_code=status.HTTP_201_CREATED)
async def upload_media(
    file: UploadFile,
    request: Request,
    uploaded_by_header: str | None = Header(default=None, alias="X-Authenticated-User-Id"),
    session: AsyncSession = Depends(get_async_session),
    storage_backend: ObjectStorage = Depends(get_storage),
) -> MediaAssetResponse:
    if uploaded_by_header is None:
        raise HTTPException(status_code=401, detail="Authenticated user id is required.")
    try:
        uploaded_by = UUID(uploaded_by_header)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Authenticated user id must be a UUID.") from exc

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file must not be empty.")

    asset_id = uuid4()
    filename = _safe_filename(file.filename)
    mime_type = file.content_type or "application/octet-stream"
    storage_path = f"assets/{asset_id}/{filename}"
    checksum = sha256(data).hexdigest()

    repository = MediaAssetRepository(session)
    try:
        await storage_backend.put_object(
            storage_path=storage_path,
            data=data,
            content_type=mime_type,
        )
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
        raise

    return MediaAssetResponse.model_validate(asset)


@router.get("/{asset_id}", response_model=MediaAssetResponse)
async def get_media_asset(
    asset_id: UUID,
    session: AsyncSession = Depends(get_async_session),
) -> MediaAssetResponse:
    repository = MediaAssetRepository(session)
    asset = await repository.get_asset(asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail=f"Media asset {asset_id} was not found.")
    return MediaAssetResponse.model_validate(asset)


@router.get("/{asset_id}/download-url", response_model=SignedDownloadUrlResponse)
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
    return SignedDownloadUrlResponse(
        asset_id=asset.id,
        url=url,
        expires_in_seconds=settings.signed_url_ttl_seconds,
    )
