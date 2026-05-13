import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_async_session
from page_service import (
    InvalidMetadataError,
    InvalidParentRevisionError,
    InvalidStatusTransitionError,
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
    PublishRevisionRequest,
    RevertRevisionRequest,
    RevisionDetailResponse,
    TransitionPageStatusRequest,
    UpdatePageMetadataRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pages", tags=["pages"])


def _get_publisher(request: Request):
    return request.app.state.publisher


@router.post("", response_model=PageDraftResponse, status_code=status.HTTP_201_CREATED)
async def create_page(
    request: Request,
    payload: CreatePageRequest,
    session: AsyncSession = Depends(get_async_session),
) -> PageDraftResponse:
    publisher = _get_publisher(request)
    service = PageService(session)
    try:
        page, revision = await service.create_page(payload)
    except PageAlreadyExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    try:
        await publisher.publish("page.created", {"page_id": str(page.id), "slug": page.slug})
    except Exception as exc:
        logger.warning("Failed to publish page.created for page %s: %s", page.id, exc)
    return PageDraftResponse(page=page, revision=revision)


@router.post(
    "/{page_id}/drafts",
    response_model=PageDraftResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_draft_revision(
    page_id: UUID,
    request: Request,
    payload: CreateDraftRevisionRequest,
    session: AsyncSession = Depends(get_async_session),
) -> PageDraftResponse:
    publisher = _get_publisher(request)
    service = PageService(session)
    try:
        page, revision = await service.create_draft_revision(page_id=page_id, payload=payload)
    except PageNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidParentRevisionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except StalePageVersionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    try:
        await publisher.publish(
            "page.revision_created",
            {"page_id": str(page.id), "revision_id": str(revision.id)},
        )
    except Exception as exc:
        logger.warning("Failed to publish page.revision_created for page %s: %s", page.id, exc)
    return PageDraftResponse(page=page, revision=revision)


@router.get("/slug/{slug}", response_model=PageStateResponse)
async def get_page_state_by_slug(
    slug: str,
    session: AsyncSession = Depends(get_async_session),
) -> PageStateResponse:
    service = PageService(session)
    try:
        page, current_draft_revision, current_published_revision = await service.get_page_state_by_slug(slug)
    except PageNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return PageStateResponse(
        page=page,
        current_draft_revision=current_draft_revision,
        current_published_revision=current_published_revision,
    )


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


@router.put("/{page_id}/metadata", response_model=PageStateResponse)
async def update_page_metadata(
    page_id: UUID,
    request: Request,
    payload: UpdatePageMetadataRequest,
    session: AsyncSession = Depends(get_async_session),
) -> PageStateResponse:
    publisher = _get_publisher(request)
    service = PageService(session)
    try:
        page, current_draft_revision, current_published_revision = await service.update_page_metadata(
            page_id=page_id,
            expected_page_version=payload.expected_page_version,
            tags=payload.tags,
            classifications=payload.classifications,
            related_page_ids=payload.related_page_ids,
            media_asset_ids=payload.media_asset_ids,
        )
    except PageNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidMetadataError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except StalePageVersionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    try:
        await publisher.publish(
            "page.metadata_updated",
            {"page_id": str(page.id)},
        )
    except Exception as exc:
        logger.warning("Failed to publish page.metadata_updated for page %s: %s", page.id, exc)
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


@router.post("/{page_id}/publish", response_model=PageStateResponse)
async def publish_revision(
    page_id: UUID,
    request: Request,
    payload: PublishRevisionRequest,
    session: AsyncSession = Depends(get_async_session),
) -> PageStateResponse:
    publisher = _get_publisher(request)
    service = PageService(session)
    try:
        page, current_draft_revision, current_published_revision = await service.publish_revision(
            page_id=page_id,
            payload=payload,
        )
    except PageNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except StalePageVersionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    try:
        await publisher.publish(
            "page.published",
            {
                "page_id": str(page.id),
                "revision_id": str(current_published_revision.id) if current_published_revision else None,
            },
        )
    except Exception as exc:
        logger.warning("Failed to publish page.published for page %s: %s", page.id, exc)
    return PageStateResponse(
        page=page,
        current_draft_revision=current_draft_revision,
        current_published_revision=current_published_revision,
    )


@router.post("/{page_id}/revert", response_model=PageDraftResponse, status_code=status.HTTP_201_CREATED)
async def revert_revision(
    page_id: UUID,
    payload: RevertRevisionRequest,
    session: AsyncSession = Depends(get_async_session),
) -> PageDraftResponse:
    service = PageService(session)
    try:
        page, revision = await service.revert_to_revision(page_id=page_id, payload=payload)
    except PageNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except StalePageVersionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return PageDraftResponse(page=page, revision=revision)


@router.post("/{page_id}/status", response_model=PageStateResponse)
async def transition_page_status(
    page_id: UUID,
    request: Request,
    payload: TransitionPageStatusRequest,
    session: AsyncSession = Depends(get_async_session),
) -> PageStateResponse:
    publisher = _get_publisher(request)
    service = PageService(session)
    try:
        page, current_draft_revision, current_published_revision = await service.transition_page_status(
            page_id=page_id,
            payload=payload,
        )
    except PageNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidStatusTransitionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except StalePageVersionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    try:
        await publisher.publish(
            "page.status_changed",
            {
                "page_id": str(page.id),
                "new_status": page.status.value,
            },
        )
    except Exception as exc:
        logger.warning("Failed to publish page.status_changed for page %s: %s", page.id, exc)
    return PageStateResponse(
        page=page,
        current_draft_revision=current_draft_revision,
        current_published_revision=current_published_revision,
    )
