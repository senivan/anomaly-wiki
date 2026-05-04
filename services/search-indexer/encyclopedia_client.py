from typing import Optional
from uuid import UUID

import httpx


class PageState:
    def __init__(
        self,
        page: dict,
        current_published_revision: Optional[dict],
        current_draft_revision: Optional[dict],
    ) -> None:
        self.page = page
        self.current_published_revision = current_published_revision
        self.current_draft_revision = current_draft_revision


class EncyclopediaClient:
    def __init__(self, http_client: httpx.AsyncClient) -> None:
        self._client = http_client

    async def get_page_state(self, page_id: UUID) -> Optional[PageState]:
        response = await self._client.get(f"/pages/{page_id}")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        data = response.json()
        return PageState(
            page=data["page"],
            current_published_revision=data.get("current_published_revision"),
            current_draft_revision=data.get("current_draft_revision"),
        )
