from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_async_session
from page_service import (
    InvalidParentRevisionError,
    PageAlreadyExistsError,
    PageNotFoundError,
    PageService,
)
from repository import StalePageVersionError
from schemas import (
    CreateDraftRevisionRequest,
    CreatePageRequest,
    PageDraftResponse,
    PageRevisionListResponse,
    PageStateResponse,
    RevisionDetailResponse,
)

router = APIRouter(prefix="/pages", tags=["pages"])


@router.post("", response_model=PageDraftResponse, status_code=status.HTTP_201_CREATED)
async def create_page(
    payload: CreatePageRequest,
    session: AsyncSession = Depends(get_async_session),
) -> PageDraftResponse:
    service = PageService(session)
    try:
        page, revision = await service.create_page(payload)
    except PageAlreadyExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return PageDraftResponse(page=page, revision=revision)


@router.post(
    "/{page_id}/drafts",
    response_model=PageDraftResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_draft_revision(
    page_id: UUID,
    payload: CreateDraftRevisionRequest,
    session: AsyncSession = Depends(get_async_session),
) -> PageDraftResponse:
    service = PageService(session)
    try:
        page, revision = await service.create_draft_revision(page_id=page_id, payload=payload)
    except PageNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidParentRevisionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except StalePageVersionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return PageDraftResponse(page=page, revision=revision)


@router.get("/{page_id}", response_model=PageStateResponse)
async def get_page_state(
    page_id: UUID,
    session: AsyncSession = Depends(get_async_session),
) -> PageStateResponse:
    service = PageService(session)
    try:
        page, current_draft_revision, current_published_revision = await service.get_page_state(page_id)
    except PageNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return PageStateResponse(
        page=page,
        current_draft_revision=current_draft_revision,
        current_published_revision=current_published_revision,
    )


@router.get("/{page_id}/revisions", response_model=PageRevisionListResponse)
async def list_page_revisions(
    page_id: UUID,
    session: AsyncSession = Depends(get_async_session),
) -> PageRevisionListResponse:
    service = PageService(session)
    try:
        page, revisions = await service.list_page_revisions(page_id)
    except PageNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return PageRevisionListResponse(page=page, revisions=revisions)


@router.get(
    "/{page_id}/revisions/{revision_id}",
    response_model=RevisionDetailResponse,
)
async def get_page_revision(
    page_id: UUID,
    revision_id: UUID,
    session: AsyncSession = Depends(get_async_session),
) -> RevisionDetailResponse:
    service = PageService(session)
    try:
        page, revision, lineage = await service.get_page_revision(
            page_id=page_id,
            revision_id=revision_id,
        )
    except PageNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return RevisionDetailResponse(page=page, revision=revision, lineage=lineage)
