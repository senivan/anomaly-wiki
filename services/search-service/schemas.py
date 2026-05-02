from typing import Optional
from pydantic import BaseModel, Field, field_validator


class SearchQuery(BaseModel):
    q: str
    type: Optional[str] = None
    visibility: Optional[str] = None
    status: Optional[str] = None
    tags: Optional[list[str]] = None
    page: int = Field(default=0, ge=0)
    size: int = Field(default=10, ge=1)

    @field_validator("size", mode="before")
    @classmethod
    def clamp_size(cls, v: int) -> int:
        return max(1, min(int(v), 50))


class SearchHit(BaseModel):
    page_id: str
    slug: str
    type: str
    title: str
    summary: str
    snippet: str
    status: str
    visibility: str


class SearchResponse(BaseModel):
    total: int
    hits: list[SearchHit]


class SuggestQuery(BaseModel):
    q: str
    type: Optional[str] = None


class SuggestResponse(BaseModel):
    suggestions: list[str]
