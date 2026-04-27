from enum import Enum
from uuid import UUID
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field

class PageType(str, Enum):
    ARTICLE = "Article"
    ANOMALY = "Anomaly"
    ARTIFACT = "Artifact"
    LOCATION = "Location"
    INCIDENT = "Incident"
    EXPEDITION = "Expedition"
    RESEARCHER_NOTE = "Researcher Note"

class PageStatus(str, Enum):
    DRAFT = "Draft"
    REVIEW = "Review"
    PUBLISHED = "Published"
    ARCHIVED = "Archived"
    REDACTED = "Redacted"

class Visibility(str, Enum):
    PUBLIC = "Public"
    INTERNAL = "Internal"

class Page(BaseModel):
    id: UUID
    slug: str
    type: PageType
    status: PageStatus
    visibility: Visibility
    current_published_revision_id: Optional[UUID] = None
    current_draft_revision_id: Optional[UUID] = None
    version: int = Field(default=1)

class Revision(BaseModel):
    id: UUID
    page_id: UUID
    parent_revision_id: Optional[UUID] = None
    author_id: Optional[UUID] = None
    title: str
    summary: str
    content: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class MediaAsset(BaseModel):
    id: UUID
    filename: str
    mime_type: str
    storage_path: str
    uploaded_by: UUID
