from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from errors import register_exception_handlers
from middleware import register_http_middleware
from routes.health import router as health_router


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="API Gateway",
        description="Single external entry point for anomaly-wiki clients.",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.cors_allowed_methods,
        allow_headers=settings.cors_allowed_headers,
    )
    register_http_middleware(app)
    register_exception_handlers(app)
    app.include_router(health_router)
    return app


app = create_app()
