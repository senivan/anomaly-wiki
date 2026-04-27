import pytest
from uuid import uuid4, UUID
from datetime import datetime, timezone
from shared.models import Page, PageType, PageStatus, Visibility, MediaAsset
from shared.events import (
    PageCreatedEvent,
    PageRevisionCreatedEvent,
    PagePublishedEvent,
    PageStatusChangedEvent,
    MediaMetadataUpdatedEvent
)

def test_page_created_event_validation():
    page = Page(
        id=uuid4(),
        slug="test-page",
        type=PageType.ARTICLE,
        status=PageStatus.DRAFT,
        visibility=Visibility.PUBLIC
    )
    event = PageCreatedEvent(page=page)
    assert event.page.id == page.id
    assert isinstance(event.event_id, UUID)
    assert isinstance(event.timestamp, datetime)
    assert event.timestamp.tzinfo == timezone.utc

def test_page_revision_created_event_validation():
    page_id = uuid4()
    revision_id = uuid4()
    event = PageRevisionCreatedEvent(page_id=page_id, revision_id=revision_id)
    assert event.page_id == page_id
    assert event.revision_id == revision_id
    assert isinstance(event.event_id, UUID)

def test_page_published_event_validation():
    page_id = uuid4()
    revision_id = uuid4()
    event = PagePublishedEvent(page_id=page_id, revision_id=revision_id)
    assert event.page_id == page_id
    assert event.revision_id == revision_id

def test_page_status_changed_event_validation():
    page_id = uuid4()
    event = PageStatusChangedEvent(
        page_id=page_id,
        old_status=PageStatus.DRAFT,
        new_status=PageStatus.REVIEW
    )
    assert event.page_id == page_id
    assert event.old_status == PageStatus.DRAFT
    assert event.new_status == PageStatus.REVIEW

def test_media_metadata_updated_event_validation():
    asset = MediaAsset(
        id=uuid4(),
        filename="test.jpg",
        mime_type="image/jpeg",
        storage_path="path/to/test.jpg",
        uploaded_by=uuid4()
    )
    event = MediaMetadataUpdatedEvent(asset=asset)
    assert event.asset.id == asset.id
