from fastapi import FastAPI

from routes.health import router as health_router

app = FastAPI(
    title="API Gateway",
    description="Single external entry point for anomaly-wiki clients.",
    version="0.1.0",
)

app.include_router(health_router)
