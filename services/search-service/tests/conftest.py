from unittest.mock import AsyncMock
from fastapi import FastAPI
from routes.search import router as search_router
from routes.health import router as health_router


def build_search_app(opensearch_response: dict) -> tuple[FastAPI, AsyncMock]:
    fake_os = AsyncMock()
    fake_os.search.return_value = opensearch_response
    fake_os.ping.return_value = True

    app = FastAPI()
    app.state.opensearch = fake_os
    app.include_router(search_router)
    app.include_router(health_router)
    return app, fake_os


def make_os_response(hits: list[dict], total: int = None) -> dict:
    if total is None:
        total = len(hits)
    return {
        "hits": {
            "total": {"value": total},
            "hits": [
                {
                    "_source": h,
                    "highlight": {
                        "content_text": [h.get("summary", "...excerpt...")],
                    },
                }
                for h in hits
            ],
        }
    }
