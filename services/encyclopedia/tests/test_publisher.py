import json
from unittest.mock import AsyncMock, MagicMock
import pytest
from publisher import EventPublisher, NoopPublisher


async def test_event_publisher_publishes_json_message():
    mock_exchange = AsyncMock()
    publisher = EventPublisher(mock_exchange)

    await publisher.publish("page.created", {"page_id": "abc-123", "slug": "test"})

    mock_exchange.publish.assert_called_once()
    call_args = mock_exchange.publish.call_args
    message = call_args.args[0]
    body = json.loads(message.body)
    assert body["page_id"] == "abc-123"
    routing_key = call_args.kwargs["routing_key"]
    assert routing_key == "page.created"


async def test_noop_publisher_does_not_raise():
    publisher = NoopPublisher()
    await publisher.publish("page.created", {"page_id": "abc-123"})
