from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from domain import PageStatus, PageType, Visibility


class Base(DeclarativeBase):
    pass


class PageRecord(Base):
    __tablename__ = "pages"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    type: Mapped[PageType] = mapped_column(
        Enum(PageType, values_callable=lambda types: [type_.value for type_ in types], name="pagetype"),
        nullable=False,
    )
    status: Mapped[PageStatus] = mapped_column(
        Enum(
            PageStatus,
            values_callable=lambda statuses: [status.value for status in statuses],
            name="pagestatus",
        ),
        default=PageStatus.DRAFT,
        server_default=PageStatus.DRAFT.value,
        nullable=False,
    )
    visibility: Mapped[Visibility] = mapped_column(
        Enum(
            Visibility,
            values_callable=lambda visibilities: [visibility.value for visibility in visibilities],
            name="visibility",
        ),
        nullable=False,
    )
    current_draft_revision_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("revisions.id"),
        nullable=True,
    )
    current_published_revision_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("revisions.id"),
        nullable=True,
    )
    version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        server_default="1",
        nullable=False,
    )
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    classifications: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    revisions: Mapped[list[RevisionRecord]] = relationship(
        back_populates="page",
        foreign_keys="RevisionRecord.page_id",
        cascade="all, delete-orphan",
        order_by="RevisionRecord.created_at",
    )
    current_draft_revision: Mapped[RevisionRecord | None] = relationship(
        foreign_keys=[current_draft_revision_id],
        post_update=True,
    )
    current_published_revision: Mapped[RevisionRecord | None] = relationship(
        foreign_keys=[current_published_revision_id],
        post_update=True,
    )
    related_pages: Mapped[list[PageRelationshipRecord]] = relationship(
        back_populates="page",
        cascade="all, delete-orphan",
        foreign_keys="PageRelationshipRecord.page_id",
    )
    media_references: Mapped[list[PageMediaReferenceRecord]] = relationship(
        back_populates="page",
        cascade="all, delete-orphan",
        foreign_keys="PageMediaReferenceRecord.page_id",
    )

    @property
    def related_page_ids(self) -> list[UUID]:
        return [relationship.target_page_id for relationship in self.related_pages]

    @property
    def media_asset_ids(self) -> list[UUID]:
        return [reference.asset_id for reference in self.media_references]


class RevisionRecord(Base):
    __tablename__ = "revisions"
    __table_args__ = (
        UniqueConstraint("page_id", "id", name="uq_revision_page_id_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    page_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("pages.id"), nullable=False, index=True)
    parent_revision_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("revisions.id"),
        nullable=True,
    )
    author_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    page: Mapped[PageRecord] = relationship(
        back_populates="revisions",
        foreign_keys=[page_id],
    )
    parent_revision: Mapped[RevisionRecord | None] = relationship(
        remote_side=[id],
        foreign_keys=[parent_revision_id],
    )


class PageRelationshipRecord(Base):
    __tablename__ = "page_relationships"
    __table_args__ = (
        UniqueConstraint("page_id", "target_page_id", name="uq_page_relationship"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    page_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("pages.id"), nullable=False, index=True)
    target_page_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("pages.id"), nullable=False, index=True)

    page: Mapped[PageRecord] = relationship(
        back_populates="related_pages",
        foreign_keys=[page_id],
    )


class PageMediaReferenceRecord(Base):
    __tablename__ = "page_media_references"
    __table_args__ = (
        UniqueConstraint("page_id", "asset_id", name="uq_page_media_reference"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    page_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("pages.id"), nullable=False, index=True)
    asset_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)

    page: Mapped[PageRecord] = relationship(
        back_populates="media_references",
        foreign_keys=[page_id],
    )
