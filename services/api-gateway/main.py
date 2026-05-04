import httpx

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from errors import register_exception_handlers
from middleware import register_http_middleware
from routes.auth import router as auth_router
from routes.health import router as health_router
from routes.media import router as media_router
from security import JwksCache


def create_app(*, upstream_transport: httpx.AsyncBaseTransport | None = None) -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="API Gateway",
        description="Single external entry point for anomaly-wiki clients.",
        version="0.1.0",
    )
    app.state.upstream_transport = upstream_transport
    app.state.jwks_cache = JwksCache()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.cors_allowed_methods,
        allow_headers=settings.cors_allowed_headers,
    )
    register_http_middleware(app)
    register_exception_handlers(app)
    app.include_router(auth_router)
    app.include_router(health_router)
    app.include_router(media_router)
    return app


app = create_app()
