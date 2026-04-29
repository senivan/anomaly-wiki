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
from schemas import CreateDraftRevisionRequest, CreatePageRequest, PageDraftResponse

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
