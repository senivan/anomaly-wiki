from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from domain import PageStatus, PageType, Visibility


class CreatePageRequest(BaseModel):
    slug: str = Field(min_length=1, max_length=255)
    type: PageType
    visibility: Visibility
    title: str = Field(min_length=1, max_length=255)
    summary: str = ""
    content: str = Field(min_length=1)
    author_id: UUID | None = None


class CreateDraftRevisionRequest(BaseModel):
    expected_page_version: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=255)
    summary: str = ""
    content: str = Field(min_length=1)
    author_id: UUID | None = None
    parent_revision_id: UUID | None = None


class PublishRevisionRequest(BaseModel):
    expected_page_version: int = Field(ge=1)
    revision_id: UUID


class RevertRevisionRequest(BaseModel):
    expected_page_version: int = Field(ge=1)
    revision_id: UUID
    author_id: UUID | None = None


class TransitionPageStatusRequest(BaseModel):
    expected_page_version: int = Field(ge=1)
    status: PageStatus


class UpdatePageMetadataRequest(BaseModel):
    expected_page_version: int = Field(ge=1)
    tags: list[str] = Field(default_factory=list)
    classifications: list[str] = Field(default_factory=list)
    related_page_ids: list[UUID] = Field(default_factory=list)
    media_asset_ids: list[UUID] = Field(default_factory=list)


class PageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    slug: str
    type: PageType
    status: PageStatus
    visibility: Visibility
    current_draft_revision_id: UUID | None
    current_published_revision_id: UUID | None
    version: int
    tags: list[str]
    classifications: list[str]
    related_page_ids: list[UUID]
    media_asset_ids: list[UUID]
    created_at: datetime
    updated_at: datetime


class RevisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    page_id: UUID
    parent_revision_id: UUID | None
    author_id: UUID | None
    title: str
    summary: str
    content: str
    created_at: datetime


class PageDraftResponse(BaseModel):
    page: PageResponse
    revision: RevisionResponse


class PageStateResponse(BaseModel):
    page: PageResponse
    current_draft_revision: RevisionResponse | None
    current_published_revision: RevisionResponse | None


class PageRevisionListResponse(BaseModel):
    page: PageResponse
    revisions: list[RevisionResponse]


class RevisionDetailResponse(BaseModel):
    page: PageResponse
    revision: RevisionResponse
    lineage: list[RevisionResponse]
