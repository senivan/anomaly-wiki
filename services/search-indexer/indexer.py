import logging
from uuid import UUID

from opensearchpy import AsyncOpenSearch

from encyclopedia_client import EncyclopediaClient
from markdown import extract_plain_text

logger = logging.getLogger(__name__)


def _build_document(page: dict, revision: dict) -> dict:
    return {
        "page_id": str(page["id"]),
        "slug": page["slug"],
        "type": page["type"],
        "status": page["status"],
        "visibility": page["visibility"],
        "tags": page.get("tags", []),
        "title": revision["title"],
        "summary": revision.get("summary", ""),
        "content_text": extract_plain_text(revision["content"]),
        "aliases": [],
    }


async def upsert_page(
    page_id: UUID,
    encyclopedia: EncyclopediaClient,
    os_client: AsyncOpenSearch,
    index: str,
) -> None:
    state = await encyclopedia.get_page_state(page_id)
    if state is None:
        logger.warning("Page %s not found, skipping index", page_id)
        return

    revision = state.current_published_revision or state.current_draft_revision
    if revision is None:
        logger.info("Page %s has no revision yet, skipping index", page_id)
        return

    doc = _build_document(state.page, revision)
    await os_client.index(index=index, id=str(page_id), body=doc)
    logger.info("Indexed page %s (%s)", page_id, doc["slug"])


async def delete_page(
    page_id: UUID,
    os_client: AsyncOpenSearch,
    index: str,
) -> None:
    try:
        await os_client.delete(index=index, id=str(page_id))
        logger.info("Deleted page %s from index", page_id)
    except Exception as exc:
        logger.warning("Failed to delete page %s: %s", page_id, exc)
