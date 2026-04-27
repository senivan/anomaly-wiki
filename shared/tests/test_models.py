import pytest
from uuid import uuid4
from datetime import datetime, timezone
from pydantic import ValidationError
from models import Page, Revision, MediaAsset, PageType, PageStatus, Visibility

def test_page_validation():
    page_id = uuid4()
    page = Page(
        id=page_id,
        slug="scp-173",
        type=PageType.ANOMALY,
        status=PageStatus.PUBLISHED,
        visibility=Visibility.PUBLIC
    )
    assert page.id == page_id
    assert page.slug == "scp-173"
    assert page.type == PageType.ANOMALY
    assert page.status == PageStatus.PUBLISHED
    assert page.visibility == Visibility.PUBLIC
    assert page.version == 1
    assert page.current_published_revision_id is None

def test_revision_validation():
    rev_id = uuid4()
    page_id = uuid4()
    author_id = uuid4()
    created_at = datetime.now(timezone.utc)
    
    revision = Revision(
        id=rev_id,
        page_id=page_id,
        author_id=author_id,
        title="The Sculpture",
        summary="Initial containment procedures",
        content="Keep eyes on it at all times.",
        created_at=created_at
    )
    
    assert revision.id == rev_id
    assert revision.page_id == page_id
    assert revision.author_id == author_id
    assert revision.title == "The Sculpture"
    assert revision.created_at == created_at

def test_media_asset_validation():
    asset_id = uuid4()
    user_id = uuid4()
    
    asset = MediaAsset(
        id=asset_id,
        filename="photo.jpg",
        mime_type="image/jpeg",
        storage_path="/assets/photo.jpg",
        uploaded_by=user_id
    )
    
    assert asset.id == asset_id
    assert asset.filename == "photo.jpg"
    assert asset.uploaded_by == user_id

def test_page_invalid_type():
    with pytest.raises(ValidationError):
        Page(
            id=uuid4(),
            slug="invalid",
            type="UnknownType",
            status=PageStatus.DRAFT,
            visibility=Visibility.PUBLIC
        )

def test_defaults():
    page = Page(
        id=uuid4(),
        slug="test",
        type=PageType.ARTICLE,
        status=PageStatus.DRAFT,
        visibility=Visibility.PUBLIC
    )
    assert page.version == 1
    
    revision = Revision(
        id=uuid4(),
        page_id=uuid4(),
        title="Test",
        summary="Test",
        content="Test"
    )
    assert isinstance(revision.created_at, datetime)
    assert revision.parent_revision_id is None

