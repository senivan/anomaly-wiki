import json
import logging
from typing import Any
from uuid import UUID

import aio_pika
from aio_pika import ExchangeType
from opensearchpy import AsyncOpenSearch
import httpx

from config import Settings
from encyclopedia_client import EncyclopediaClient
from indexer import delete_page, upsert_page

logger = logging.getLogger(__name__)

_UPSERT_ROUTING_KEYS = {"page.created", "page.revision_created", "page.published", "page.metadata_updated"}
_TERMINAL_STATUSES = {"Archived", "Redacted"}


async def _handle_message(
    routing_key: str,
    body: dict[str, Any],
    encyclopedia: EncyclopediaClient,
    os_client: AsyncOpenSearch,
    index: str,
) -> None:
    if routing_key in _UPSERT_ROUTING_KEYS:
        page_id = UUID(body["page_id"])
        await upsert_page(page_id, encyclopedia, os_client, index)
    elif routing_key == "page.status_changed":
        page_id = UUID(body["page_id"])
        new_status = body["new_status"]
        if new_status in _TERMINAL_STATUSES:
            await delete_page(page_id, os_client, index)
        else:
            await upsert_page(page_id, encyclopedia, os_client, index)
    else:
        logger.debug("Ignored routing key: %s", routing_key)


async def run_consumer(settings: Settings) -> None:
    os_client = AsyncOpenSearch(hosts=[settings.opensearch_url.rstrip("/")])
    http_client = httpx.AsyncClient(base_url=settings.encyclopedia_url)
    encyclopedia = EncyclopediaClient(http_client)

    try:
        connection = await aio_pika.connect_robust(settings.rabbitmq_url)
        async with connection:
            channel = await connection.channel()
            exchange = await channel.declare_exchange(
                settings.exchange_name, ExchangeType.TOPIC, durable=True
            )
            queue = await channel.declare_queue(settings.queue_name, durable=True)
            await queue.bind(exchange, routing_key="page.*")

            logger.info("Search indexer listening on queue '%s'", settings.queue_name)

            async with queue.iterator() as queue_iter:
                async for message in queue_iter:
                    try:
                        body = json.loads(message.body)
                    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                        logger.error("Malformed message body, rejecting: %s", exc)
                        await message.reject(requeue=False)
                        continue

                    async with message.process(requeue=True, ignore_processed=True):
                        try:
                            await _handle_message(
                                routing_key=message.routing_key,
                                body=body,
                                encyclopedia=encyclopedia,
                                os_client=os_client,
                                index=settings.opensearch_index,
                            )
                        except (KeyError, ValueError) as exc:
                            logger.error(
                                "Invalid message schema for routing key %s, rejecting: %s",
                                message.routing_key,
                                exc,
                            )
                            await message.reject(requeue=False)
    finally:
        await http_client.aclose()
        await os_client.close()
