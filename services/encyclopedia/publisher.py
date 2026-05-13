import json
import logging
from typing import Optional

import aio_pika
from aio_pika import ExchangeType, Message, DeliveryMode

logger = logging.getLogger(__name__)

EXCHANGE_NAME = "encyclopedia.events"


class EventPublisher:
    def __init__(self, exchange: aio_pika.Exchange) -> None:
        self._exchange = exchange

    async def publish(self, routing_key: str, body: dict) -> None:
        message = Message(
            body=json.dumps(body, default=str).encode(),
            content_type="application/json",
            delivery_mode=DeliveryMode.PERSISTENT,
        )
        await self._exchange.publish(message, routing_key=routing_key)
        logger.debug("Published %s", routing_key)


class NoopPublisher:
    async def publish(self, routing_key: str, body: dict) -> None:
        logger.debug("Noop publish: %s", routing_key)


async def connect_publisher(
    rabbitmq_url: Optional[str],
) -> tuple[Optional[aio_pika.RobustConnection], "EventPublisher | NoopPublisher"]:
    if not rabbitmq_url:
        return None, NoopPublisher()
    connection = await aio_pika.connect_robust(rabbitmq_url)
    channel = await connection.channel()
    exchange = await channel.declare_exchange(
        EXCHANGE_NAME, ExchangeType.TOPIC, durable=True
    )
    return connection, EventPublisher(exchange)
