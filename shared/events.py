from uuid import UUID, uuid4
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from shared.models import Page, MediaAsset, PageStatus

class BaseEvent(BaseModel):
    event_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class PageCreatedEvent(BaseEvent):
    page: Page

class PageRevisionCreatedEvent(BaseEvent):
    page_id: UUID
    revision_id: UUID

class PagePublishedEvent(BaseEvent):
    page_id: UUID
    revision_id: UUID

class PageStatusChangedEvent(BaseEvent):
    page_id: UUID
    old_status: PageStatus
    new_status: PageStatus

class MediaMetadataUpdatedEvent(BaseEvent):
    asset: MediaAsset
