from __future__ import annotations

from dataclasses import dataclass
from typing import Final
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from domain import PageStatus, PageType, Visibility
from models import PageRecord, RevisionRecord

UNSET: Final = object()


class StalePageVersionError(Exception):
    pass


@dataclass
class PageRepository:
    session: AsyncSession

    async def create_page(
        self,
        *,
        slug: str,
        page_type: PageType,
        visibility: Visibility,
        status: PageStatus = PageStatus.DRAFT,
    ) -> PageRecord:
        page = PageRecord(
            slug=slug,
            type=page_type,
            visibility=visibility,
            status=status,
        )
        self.session.add(page)
        await self.session.flush()
        return page

    async def create_revision(
        self,
        *,
        page_id: UUID,
        title: str,
        summary: str,
        content: str,
        parent_revision_id: UUID | None = None,
        author_id: UUID | None = None,
    ) -> RevisionRecord:
        revision = RevisionRecord(
            page_id=page_id,
            parent_revision_id=parent_revision_id,
            author_id=author_id,
            title=title,
            summary=summary,
            content=content,
        )
        self.session.add(revision)
        await self.session.flush()
        return revision

    async def get_page(self, page_id: UUID) -> PageRecord | None:
        return await self.session.get(PageRecord, page_id)

    async def get_page_by_slug(self, slug: str) -> PageRecord | None:
        result = await self.session.execute(
            select(PageRecord).where(PageRecord.slug == slug)
        )
        return result.scalar_one_or_none()

    async def get_revision(self, revision_id: UUID) -> RevisionRecord | None:
        return await self.session.get(RevisionRecord, revision_id)

    async def list_revisions(self, page_id: UUID) -> list[RevisionRecord]:
        result = await self.session.execute(
            select(RevisionRecord)
            .where(RevisionRecord.page_id == page_id)
            .order_by(RevisionRecord.created_at, RevisionRecord.id)
        )
        return list(result.scalars())

    async def get_revision_lineage(self, revision_id: UUID) -> list[RevisionRecord]:
        lineage: list[RevisionRecord] = []
        current = await self.get_revision(revision_id)
        while current is not None:
            lineage.append(current)
            if current.parent_revision_id is None:
                break
            current = await self.get_revision(current.parent_revision_id)
        return lineage

    async def update_page_state(
        self,
        *,
        page_id: UUID,
        expected_version: int,
        current_draft_revision_id: UUID | None | object = UNSET,
        current_published_revision_id: UUID | None | object = UNSET,
        status: PageStatus | object = UNSET,
    ) -> PageRecord:
        page = await self.get_page(page_id)
        if page is None:
            raise LookupError(f"Page {page_id} was not found.")

        values: dict[str, object] = {"version": PageRecord.version + 1}
        if current_draft_revision_id is not UNSET:
            values["current_draft_revision_id"] = current_draft_revision_id
        if current_published_revision_id is not UNSET:
            values["current_published_revision_id"] = current_published_revision_id
        if status is not UNSET:
            values["status"] = status

        result = await self.session.execute(
            update(PageRecord)
            .where(
                PageRecord.id == page_id,
                PageRecord.version == expected_version,
            )
            .values(**values)
        )
        if result.rowcount != 1:
            current_page = await self.get_page(page_id)
            current_version = current_page.version if current_page is not None else "missing"
            raise StalePageVersionError(
                f"Expected page version {expected_version}, found {current_version}."
            )

        await self.session.flush()
        updated_page = await self.session.get(PageRecord, page_id, populate_existing=True)
        if updated_page is None:
            raise LookupError(f"Page {page_id} was not found after update.")
        return updated_page
