from unittest.mock import ANY, AsyncMock, patch
from uuid import uuid4

from consumer import _handle_message


async def test_page_published_event_triggers_upsert():
    page_id = uuid4()
    with patch("consumer.upsert_page", new_callable=AsyncMock) as mock_upsert, \
         patch("consumer.delete_page", new_callable=AsyncMock) as mock_delete:
        await _handle_message(
            routing_key="page.published",
            body={"page_id": str(page_id), "revision_id": str(uuid4())},
            encyclopedia=AsyncMock(),
            os_client=AsyncMock(),
            index="test-index",
        )
        mock_upsert.assert_called_once_with(page_id, ANY, ANY, "test-index")
        mock_delete.assert_not_called()


async def test_page_created_event_triggers_upsert():
    page_id = uuid4()
    with patch("consumer.upsert_page", new_callable=AsyncMock) as mock_upsert, \
         patch("consumer.delete_page", new_callable=AsyncMock) as mock_delete:
        await _handle_message(
            routing_key="page.created",
            body={"page_id": str(page_id), "slug": "fire-anomaly"},
            encyclopedia=AsyncMock(),
            os_client=AsyncMock(),
            index="test-index",
        )
        mock_upsert.assert_called_once_with(page_id, ANY, ANY, "test-index")
        mock_delete.assert_not_called()


async def test_page_revision_created_event_triggers_upsert():
    page_id = uuid4()
    with patch("consumer.upsert_page", new_callable=AsyncMock) as mock_upsert, \
         patch("consumer.delete_page", new_callable=AsyncMock) as mock_delete:
        await _handle_message(
            routing_key="page.revision_created",
            body={"page_id": str(page_id), "revision_id": str(uuid4())},
            encyclopedia=AsyncMock(),
            os_client=AsyncMock(),
            index="test-index",
        )
        mock_upsert.assert_called_once_with(page_id, ANY, ANY, "test-index")
        mock_delete.assert_not_called()


async def test_status_changed_to_archived_triggers_delete():
    page_id = uuid4()
    with patch("consumer.upsert_page", new_callable=AsyncMock) as mock_upsert, \
         patch("consumer.delete_page", new_callable=AsyncMock) as mock_delete:
        await _handle_message(
            routing_key="page.status_changed",
            body={"page_id": str(page_id), "old_status": "Published", "new_status": "Archived"},
            encyclopedia=AsyncMock(),
            os_client=AsyncMock(),
            index="test-index",
        )
        mock_delete.assert_called_once_with(page_id, ANY, "test-index")
        mock_upsert.assert_not_called()


async def test_status_changed_to_redacted_triggers_delete():
    page_id = uuid4()
    with patch("consumer.upsert_page", new_callable=AsyncMock) as mock_upsert, \
         patch("consumer.delete_page", new_callable=AsyncMock) as mock_delete:
        await _handle_message(
            routing_key="page.status_changed",
            body={"page_id": str(page_id), "old_status": "Published", "new_status": "Redacted"},
            encyclopedia=AsyncMock(),
            os_client=AsyncMock(),
            index="test-index",
        )
        mock_delete.assert_called_once_with(page_id, ANY, "test-index")
        mock_upsert.assert_not_called()


async def test_status_changed_to_published_triggers_upsert():
    page_id = uuid4()
    with patch("consumer.upsert_page", new_callable=AsyncMock) as mock_upsert, \
         patch("consumer.delete_page", new_callable=AsyncMock) as mock_delete:
        await _handle_message(
            routing_key="page.status_changed",
            body={"page_id": str(page_id), "old_status": "Draft", "new_status": "Published"},
            encyclopedia=AsyncMock(),
            os_client=AsyncMock(),
            index="test-index",
        )
        mock_upsert.assert_called_once_with(page_id, ANY, ANY, "test-index")
        mock_delete.assert_not_called()


async def test_unknown_routing_key_is_noop():
    with patch("consumer.upsert_page", new_callable=AsyncMock) as mock_upsert, \
         patch("consumer.delete_page", new_callable=AsyncMock) as mock_delete:
        await _handle_message(
            routing_key="media.metadata_updated",
            body={"asset": {}},
            encyclopedia=AsyncMock(),
            os_client=AsyncMock(),
            index="test-index",
        )
        mock_upsert.assert_not_called()
        mock_delete.assert_not_called()


async def test_status_changed_to_draft_triggers_upsert():
    page_id = uuid4()
    with patch("consumer.upsert_page", new_callable=AsyncMock) as mock_upsert, \
         patch("consumer.delete_page", new_callable=AsyncMock) as mock_delete:
        await _handle_message(
            routing_key="page.status_changed",
            body={"page_id": str(page_id), "old_status": "Published", "new_status": "Draft"},
            encyclopedia=AsyncMock(),
            os_client=AsyncMock(),
            index="test-index",
        )
        mock_upsert.assert_called_once_with(page_id, ANY, ANY, "test-index")
        mock_delete.assert_not_called()


async def test_status_changed_to_review_triggers_upsert():
    page_id = uuid4()
    with patch("consumer.upsert_page", new_callable=AsyncMock) as mock_upsert, \
         patch("consumer.delete_page", new_callable=AsyncMock) as mock_delete:
        await _handle_message(
            routing_key="page.status_changed",
            body={"page_id": str(page_id), "old_status": "Published", "new_status": "Review"},
            encyclopedia=AsyncMock(),
            os_client=AsyncMock(),
            index="test-index",
        )
        mock_upsert.assert_called_once_with(page_id, ANY, ANY, "test-index")
        mock_delete.assert_not_called()


async def test_metadata_updated_event_triggers_upsert():
    page_id = uuid4()
    with patch("consumer.upsert_page", new_callable=AsyncMock) as mock_upsert, \
         patch("consumer.delete_page", new_callable=AsyncMock) as mock_delete:
        await _handle_message(
            routing_key="page.metadata_updated",
            body={"page_id": str(page_id)},
            encyclopedia=AsyncMock(),
            os_client=AsyncMock(),
            index="test-index",
        )
        mock_upsert.assert_called_once_with(page_id, ANY, ANY, "test-index")
        mock_delete.assert_not_called()
