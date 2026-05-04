from unittest.mock import AsyncMock
from uuid import uuid4
import pytest
from consumer import _handle_message

PAGE_ID = uuid4()
REVISION_ID = uuid4()


async def test_page_published_event_triggers_upsert():
    enc = AsyncMock()
    os = AsyncMock()
    enc.get_page_state.return_value = None

    await _handle_message(
        routing_key="page.published",
        body={"page_id": str(PAGE_ID), "revision_id": str(REVISION_ID)},
        encyclopedia=enc,
        os_client=os,
        index="test-index",
    )

    enc.get_page_state.assert_called_once_with(PAGE_ID)


async def test_page_created_event_triggers_upsert():
    enc = AsyncMock()
    os = AsyncMock()
    enc.get_page_state.return_value = None

    await _handle_message(
        routing_key="page.created",
        body={"page_id": str(PAGE_ID), "slug": "fire-anomaly"},
        encyclopedia=enc,
        os_client=os,
        index="test-index",
    )

    enc.get_page_state.assert_called_once_with(PAGE_ID)


async def test_page_revision_created_event_triggers_upsert():
    enc = AsyncMock()
    os = AsyncMock()
    enc.get_page_state.return_value = None

    await _handle_message(
        routing_key="page.revision_created",
        body={"page_id": str(PAGE_ID), "revision_id": str(REVISION_ID)},
        encyclopedia=enc,
        os_client=os,
        index="test-index",
    )

    enc.get_page_state.assert_called_once_with(PAGE_ID)


async def test_status_changed_to_archived_triggers_delete():
    enc = AsyncMock()
    os = AsyncMock()

    await _handle_message(
        routing_key="page.status_changed",
        body={"page_id": str(PAGE_ID), "old_status": "Published", "new_status": "Archived"},
        encyclopedia=enc,
        os_client=os,
        index="test-index",
    )

    os.delete.assert_called_once_with(index="test-index", id=str(PAGE_ID))
    enc.get_page_state.assert_not_called()


async def test_status_changed_to_redacted_triggers_delete():
    enc = AsyncMock()
    os = AsyncMock()

    await _handle_message(
        routing_key="page.status_changed",
        body={"page_id": str(PAGE_ID), "old_status": "Published", "new_status": "Redacted"},
        encyclopedia=enc,
        os_client=os,
        index="test-index",
    )

    os.delete.assert_called_once_with(index="test-index", id=str(PAGE_ID))


async def test_status_changed_to_published_triggers_upsert():
    enc = AsyncMock()
    os = AsyncMock()
    enc.get_page_state.return_value = None

    await _handle_message(
        routing_key="page.status_changed",
        body={"page_id": str(PAGE_ID), "old_status": "Draft", "new_status": "Published"},
        encyclopedia=enc,
        os_client=os,
        index="test-index",
    )

    enc.get_page_state.assert_called_once_with(PAGE_ID)
    os.delete.assert_not_called()


async def test_unknown_routing_key_is_noop():
    enc = AsyncMock()
    os = AsyncMock()

    await _handle_message(
        routing_key="media.metadata_updated",
        body={"asset": {}},
        encyclopedia=enc,
        os_client=os,
        index="test-index",
    )

    enc.get_page_state.assert_not_called()
    os.index.assert_not_called()
    os.delete.assert_not_called()
