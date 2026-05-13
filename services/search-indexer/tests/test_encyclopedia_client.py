from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
import pytest
from encyclopedia_client import EncyclopediaClient, PageState

PAGE_ID = uuid4()

FULL_PAGE_RESPONSE = {
    "page": {
        "id": str(PAGE_ID),
        "slug": "fire-anomaly",
        "type": "Anomaly",
        "status": "Published",
        "visibility": "Public",
        "tags": ["fire", "thermal"],
        "classifications": [],
    },
    "current_published_revision": {
        "id": str(uuid4()),
        "page_id": str(PAGE_ID),
        "title": "Fire Anomaly",
        "summary": "A thermal anomaly near Agroprom.",
        "content": "# Fire Anomaly\n\nVery hot.",
    },
    "current_draft_revision": None,
}


def _make_http_client(status_code: int, json_body: dict) -> AsyncMock:
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_body
    response.raise_for_status = MagicMock()
    http_client = AsyncMock()
    http_client.get.return_value = response
    return http_client


async def test_get_page_state_returns_state_on_200():
    http_client = _make_http_client(200, FULL_PAGE_RESPONSE)
    enc = EncyclopediaClient(http_client)
    state = await enc.get_page_state(PAGE_ID)
    assert isinstance(state, PageState)
    assert state.page["slug"] == "fire-anomaly"
    assert state.current_published_revision["title"] == "Fire Anomaly"
    assert state.current_draft_revision is None


async def test_get_page_state_returns_none_on_404():
    response = MagicMock()
    response.status_code = 404
    http_client = AsyncMock()
    http_client.get.return_value = response
    enc = EncyclopediaClient(http_client)
    state = await enc.get_page_state(PAGE_ID)
    assert state is None


async def test_get_page_state_calls_correct_url():
    http_client = _make_http_client(200, FULL_PAGE_RESPONSE)
    enc = EncyclopediaClient(http_client)
    await enc.get_page_state(PAGE_ID)
    http_client.get.assert_called_once_with(f"/pages/{PAGE_ID}")
