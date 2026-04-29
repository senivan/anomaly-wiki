from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from domain import PageStatus, PageType, Visibility
from models import Base
from repository import PageRepository, StalePageVersionError


async def test_create_all_builds_page_and_revision_tables() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        table_names = await connection.run_sync(
            lambda sync_connection: inspect(sync_connection).get_table_names()
        )

    assert sorted(table_names) == ["pages", "revisions"]
    await engine.dispose()


async def test_revision_storage_preserves_lineage_and_distinct_page_pointers() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_maker() as session:
        repository = PageRepository(session)
        page = await repository.create_page(
            slug="zone-anomaly",
            page_type=PageType.ANOMALY,
            visibility=Visibility.PUBLIC,
        )
        first_revision = await repository.create_revision(
            page_id=page.id,
            title="Zone Anomaly",
            summary="First summary",
            content="Initial body",
        )
        await repository.update_page_state(
            page_id=page.id,
            expected_version=page.version,
            current_draft_revision_id=first_revision.id,
            current_published_revision_id=first_revision.id,
            status=PageStatus.PUBLISHED,
        )

        second_revision = await repository.create_revision(
            page_id=page.id,
            parent_revision_id=first_revision.id,
            title="Zone Anomaly",
            summary="Updated summary",
            content="Draft body",
        )
        await repository.update_page_state(
            page_id=page.id,
            expected_version=page.version,
            current_draft_revision_id=second_revision.id,
            status=PageStatus.DRAFT,
        )
        await session.commit()

        revisions = await repository.list_revisions(page.id)
        lineage = await repository.get_revision_lineage(second_revision.id)
        refreshed_page = await repository.get_page(page.id)

    assert len(revisions) == 2
    assert [revision.id for revision in lineage] == [second_revision.id, first_revision.id]
    assert refreshed_page is not None
    assert refreshed_page.current_published_revision_id == first_revision.id
    assert refreshed_page.current_draft_revision_id == second_revision.id
    assert refreshed_page.version == 3
    await engine.dispose()


async def test_page_state_updates_reject_stale_versions() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_maker() as session:
        repository = PageRepository(session)
        page = await repository.create_page(
            slug="artifact-record",
            page_type=PageType.ARTIFACT,
            visibility=Visibility.INTERNAL,
        )
        revision = await repository.create_revision(
            page_id=page.id,
            title="Artifact Record",
            summary="Seed revision",
            content="Body",
        )
        await repository.update_page_state(
            page_id=page.id,
            expected_version=page.version,
            current_draft_revision_id=revision.id,
        )

        try:
            await repository.update_page_state(
                page_id=page.id,
                expected_version=1,
                current_published_revision_id=revision.id,
            )
        except StalePageVersionError:
            pass
        else:
            raise AssertionError("Expected stale page version to be rejected.")

    await engine.dispose()
