from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field


class MediaAssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    filename: str
    mime_type: str
    size_bytes: int
    storage_path: str
    uploaded_by: UUID
    checksum_sha256: str
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def content_type(self) -> str:
        return self.mime_type


class SignedDownloadUrlResponse(BaseModel):
    asset_id: UUID
    url: str
    expires_in_seconds: int = Field(ge=1)
