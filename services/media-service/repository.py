from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from models import MediaAssetRecord


@dataclass
class MediaAssetRepository:
    session: AsyncSession

    async def create_asset(
        self,
        *,
        asset_id: UUID,
        filename: str,
        mime_type: str,
        size_bytes: int,
        storage_path: str,
        uploaded_by: UUID,
        checksum_sha256: str,
    ) -> MediaAssetRecord:
        asset = MediaAssetRecord(
            id=asset_id,
            filename=filename,
            mime_type=mime_type,
            size_bytes=size_bytes,
            storage_path=storage_path,
            uploaded_by=uploaded_by,
            checksum_sha256=checksum_sha256,
        )
        self.session.add(asset)
        await self.session.flush()
        return asset

    async def get_asset(self, asset_id: UUID) -> MediaAssetRecord | None:
        return await self.session.get(MediaAssetRecord, asset_id)
