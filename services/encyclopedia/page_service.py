from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from domain import PageStatus
from models import PageRecord, RevisionRecord
from repository import PageRepository, StalePageVersionError
from schemas import (
    CreateDraftRevisionRequest,
    CreatePageRequest,
    PublishRevisionRequest,
    RevertRevisionRequest,
    TransitionPageStatusRequest,
)


class PageAlreadyExistsError(Exception):
    pass


class PageNotFoundError(Exception):
    pass


class InvalidParentRevisionError(Exception):
    pass


class InvalidStatusTransitionError(Exception):
    pass


ALLOWED_STATUS_TRANSITIONS = {
    PageStatus.DRAFT: {PageStatus.REVIEW, PageStatus.ARCHIVED, PageStatus.REDACTED},
    PageStatus.REVIEW: {PageStatus.DRAFT, PageStatus.ARCHIVED, PageStatus.REDACTED},
    PageStatus.PUBLISHED: {PageStatus.DRAFT, PageStatus.ARCHIVED, PageStatus.REDACTED},
    PageStatus.ARCHIVED: {PageStatus.DRAFT, PageStatus.REDACTED},
    PageStatus.REDACTED: set(),
}


@dataclass
class PageService:
    session: AsyncSession

    async def create_page(self, payload: CreatePageRequest) -> tuple[PageRecord, RevisionRecord]:
        repository = PageRepository(self.session)
        try:
            page = await repository.create_page(
                slug=payload.slug,
                page_type=payload.type,
                visibility=payload.visibility,
            )
            revision = await repository.create_revision(
                page_id=page.id,
                title=payload.title,
                summary=payload.summary,
                content=payload.content,
                author_id=payload.author_id,
            )
            page = await repository.update_page_state(
                page_id=page.id,
                expected_version=page.version,
                current_draft_revision_id=revision.id,
            )
            await self.session.commit()
            await self.session.refresh(revision)
            return page, revision
        except IntegrityError as exc:
            await self.session.rollback()
            raise PageAlreadyExistsError(
                f"Page with slug '{payload.slug}' already exists."
            ) from exc
        except Exception:
            await self.session.rollback()
            raise

    async def create_draft_revision(
        self,
        *,
        page_id: UUID,
        payload: CreateDraftRevisionRequest,
    ) -> tuple[PageRecord, RevisionRecord]:
        repository = PageRepository(self.session)
        page = await repository.get_page(page_id)
        if page is None:
            raise PageNotFoundError(f"Page {page_id} was not found.")

        parent_revision_id = payload.parent_revision_id or page.current_draft_revision_id
        if parent_revision_id is None:
            parent_revision_id = page.current_published_revision_id
        if parent_revision_id is not None:
            parent_revision = await repository.get_revision(parent_revision_id)
            if parent_revision is None or parent_revision.page_id != page.id:
                raise InvalidParentRevisionError(
                    f"Revision {parent_revision_id} cannot be used as a parent for page {page.id}."
                )

        try:
            revision = await repository.create_revision(
                page_id=page.id,
                parent_revision_id=parent_revision_id,
                title=payload.title,
                summary=payload.summary,
                content=payload.content,
                author_id=payload.author_id,
            )
            page = await repository.update_page_state(
                page_id=page.id,
                expected_version=payload.expected_page_version,
                current_draft_revision_id=revision.id,
                status=PageStatus.DRAFT,
            )
            await self.session.commit()
            await self.session.refresh(revision)
            return page, revision
        except StalePageVersionError:
            await self.session.rollback()
            raise
        except Exception:
            await self.session.rollback()
            raise

    async def get_page_state(self, page_id: UUID) -> tuple[PageRecord, RevisionRecord | None, RevisionRecord | None]:
        repository = PageRepository(self.session)
        page = await repository.get_page(page_id)
        if page is None:
            raise PageNotFoundError(f"Page {page_id} was not found.")

        current_draft_revision = None
        if page.current_draft_revision_id is not None:
            current_draft_revision = await repository.get_revision(page.current_draft_revision_id)

        current_published_revision = None
        if page.current_published_revision_id is not None:
            current_published_revision = await repository.get_revision(page.current_published_revision_id)

        return page, current_draft_revision, current_published_revision

    async def list_page_revisions(self, page_id: UUID) -> tuple[PageRecord, list[RevisionRecord]]:
        repository = PageRepository(self.session)
        page = await repository.get_page(page_id)
        if page is None:
            raise PageNotFoundError(f"Page {page_id} was not found.")

        revisions = await repository.list_revisions(page.id)
        return page, revisions

    async def get_page_revision(
        self,
        *,
        page_id: UUID,
        revision_id: UUID,
    ) -> tuple[PageRecord, RevisionRecord, list[RevisionRecord]]:
        repository = PageRepository(self.session)
        page = await repository.get_page(page_id)
        if page is None:
            raise PageNotFoundError(f"Page {page_id} was not found.")

        revision = await repository.get_revision_for_page(page_id=page.id, revision_id=revision_id)
        if revision is None:
            raise PageNotFoundError(
                f"Revision {revision_id} was not found for page {page.id}."
            )

        lineage = await repository.get_revision_lineage(revision.id)
        return page, revision, lineage

    async def publish_revision(
        self,
        *,
        page_id: UUID,
        payload: PublishRevisionRequest,
    ) -> tuple[PageRecord, RevisionRecord | None, RevisionRecord | None]:
        repository = PageRepository(self.session)
        page = await repository.get_page(page_id)
        if page is None:
            raise PageNotFoundError(f"Page {page_id} was not found.")

        revision = await repository.get_revision_for_page(
            page_id=page.id,
            revision_id=payload.revision_id,
        )
        if revision is None:
            raise PageNotFoundError(
                f"Revision {payload.revision_id} was not found for page {page.id}."
            )

        try:
            page = await repository.update_page_state(
                page_id=page.id,
                expected_version=payload.expected_page_version,
                current_published_revision_id=revision.id,
                status=PageStatus.PUBLISHED,
            )
            await self.session.commit()
            current_draft_revision = None
            if page.current_draft_revision_id is not None:
                current_draft_revision = await repository.get_revision(page.current_draft_revision_id)
            return page, current_draft_revision, revision
        except StalePageVersionError:
            await self.session.rollback()
            raise
        except Exception:
            await self.session.rollback()
            raise

    async def revert_to_revision(
        self,
        *,
        page_id: UUID,
        payload: RevertRevisionRequest,
    ) -> tuple[PageRecord, RevisionRecord]:
        repository = PageRepository(self.session)
        page = await repository.get_page(page_id)
        if page is None:
            raise PageNotFoundError(f"Page {page_id} was not found.")

        target_revision = await repository.get_revision_for_page(
            page_id=page.id,
            revision_id=payload.revision_id,
        )
        if target_revision is None:
            raise PageNotFoundError(
                f"Revision {payload.revision_id} was not found for page {page.id}."
            )

        try:
            revision = await repository.create_revision(
                page_id=page.id,
                parent_revision_id=target_revision.id,
                title=target_revision.title,
                summary=target_revision.summary,
                content=target_revision.content,
                author_id=payload.author_id,
            )
            page = await repository.update_page_state(
                page_id=page.id,
                expected_version=payload.expected_page_version,
                current_draft_revision_id=revision.id,
                status=PageStatus.DRAFT,
            )
            await self.session.commit()
            await self.session.refresh(revision)
            return page, revision
        except StalePageVersionError:
            await self.session.rollback()
            raise
        except Exception:
            await self.session.rollback()
            raise

    async def transition_page_status(
        self,
        *,
        page_id: UUID,
        payload: TransitionPageStatusRequest,
    ) -> tuple[PageRecord, RevisionRecord | None, RevisionRecord | None]:
        repository = PageRepository(self.session)
        page = await repository.get_page(page_id)
        if page is None:
            raise PageNotFoundError(f"Page {page_id} was not found.")

        if payload.status not in ALLOWED_STATUS_TRANSITIONS[page.status]:
            raise InvalidStatusTransitionError(
                f"Status transition from {page.status.value} to {payload.status.value} is not allowed."
            )

        try:
            page = await repository.update_page_state(
                page_id=page.id,
                expected_version=payload.expected_page_version,
                status=payload.status,
            )
            await self.session.commit()
            current_draft_revision = None
            if page.current_draft_revision_id is not None:
                current_draft_revision = await repository.get_revision(page.current_draft_revision_id)
            current_published_revision = None
            if page.current_published_revision_id is not None:
                current_published_revision = await repository.get_revision(page.current_published_revision_id)
            return page, current_draft_revision, current_published_revision
        except StalePageVersionError:
            await self.session.rollback()
            raise
        except Exception:
            await self.session.rollback()
            raise
