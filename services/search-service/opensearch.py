from fastapi import Request
from opensearchpy import AsyncOpenSearch

from config import Settings


def create_opensearch_client(settings: Settings) -> AsyncOpenSearch:
    url = str(settings.opensearch_url).rstrip("/")
    return AsyncOpenSearch(hosts=[url])


def get_opensearch_client(request: Request) -> AsyncOpenSearch:
    return request.app.state.opensearch
