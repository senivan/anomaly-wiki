from unittest.mock import AsyncMock
from uuid import uuid4
import pytest
from encyclopedia_client import PageState
from indexer import _build_document, upsert_page, delete_page

PAGE_ID = uuid4()

SAMPLE_PAGE = {
    "id": str(PAGE_ID),
    "slug": "fire-anomaly",
    "type": "Anomaly",
    "status": "Published",
    "visibility": "Public",
    "tags": ["fire", "thermal"],
}

SAMPLE_REVISION = {
    "id": str(uuid4()),
    "page_id": str(PAGE_ID),
    "title": "Fire Anomaly",
    "summary": "A thermal anomaly near Agroprom.",
    "content": "# Fire Anomaly\n\n**Very hot.** Dangerous.",
}


def test_build_document_maps_fields_correctly():
    doc = _build_document(SAMPLE_PAGE, SAMPLE_REVISION)
    assert doc["page_id"] == str(PAGE_ID)
    assert doc["slug"] == "fire-anomaly"
    assert doc["type"] == "Anomaly"
    assert doc["status"] == "Published"
    assert doc["visibility"] == "Public"
    assert doc["tags"] == ["fire", "thermal"]
    assert doc["title"] == "Fire Anomaly"
    assert doc["summary"] == "A thermal anomaly near Agroprom."


def test_build_document_strips_markdown_from_content():
    doc = _build_document(SAMPLE_PAGE, SAMPLE_REVISION)
    assert "#" not in doc["content_text"]
    assert "**" not in doc["content_text"]
    assert "Fire Anomaly" in doc["content_text"]
    assert "Very hot." in doc["content_text"]


def test_build_document_has_aliases_field():
    doc = _build_document(SAMPLE_PAGE, SAMPLE_REVISION)
    assert "aliases" in doc
    assert isinstance(doc["aliases"], list)


async def test_upsert_page_indexes_using_published_revision():
    os_client = AsyncMock()
    enc_client = AsyncMock()
    state = PageState(
        page=SAMPLE_PAGE,
        current_published_revision=SAMPLE_REVISION,
        current_draft_revision=None,
    )
    enc_client.get_page_state.return_value = state

    await upsert_page(PAGE_ID, enc_client, os_client, "test-index")

    os_client.index.assert_called_once()
    call_kwargs = os_client.index.call_args.kwargs
    assert call_kwargs["index"] == "test-index"
    assert call_kwargs["id"] == str(PAGE_ID)
    assert call_kwargs["body"]["slug"] == "fire-anomaly"


async def test_upsert_page_falls_back_to_draft_when_no_published_revision():
    os_client = AsyncMock()
    enc_client = AsyncMock()
    draft_revision = {**SAMPLE_REVISION, "id": str(uuid4())}
    state = PageState(
        page=SAMPLE_PAGE,
        current_published_revision=None,
        current_draft_revision=draft_revision,
    )
    enc_client.get_page_state.return_value = state

    await upsert_page(PAGE_ID, enc_client, os_client, "test-index")

    os_client.index.assert_called_once()


async def test_upsert_page_skips_when_no_revisions():
    os_client = AsyncMock()
    enc_client = AsyncMock()
    state = PageState(
        page=SAMPLE_PAGE,
        current_published_revision=None,
        current_draft_revision=None,
    )
    enc_client.get_page_state.return_value = state

    await upsert_page(PAGE_ID, enc_client, os_client, "test-index")

    os_client.index.assert_not_called()


async def test_upsert_page_skips_when_page_not_found():
    os_client = AsyncMock()
    enc_client = AsyncMock()
    enc_client.get_page_state.return_value = None

    await upsert_page(PAGE_ID, enc_client, os_client, "test-index")

    os_client.index.assert_not_called()


async def test_delete_page_calls_os_delete_with_correct_args():
    os_client = AsyncMock()

    await delete_page(PAGE_ID, os_client, "test-index")

    os_client.delete.assert_called_once_with(index="test-index", id=str(PAGE_ID))


async def test_delete_page_does_not_raise_on_os_error():
    os_client = AsyncMock()
    os_client.delete.side_effect = Exception("not found")

    await delete_page(PAGE_ID, os_client, "test-index")
