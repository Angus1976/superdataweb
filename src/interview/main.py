"""FastAPI application entry point for the interview service."""

from __future__ import annotations

from fastapi import FastAPI
from prometheus_client import make_asgi_app

from src.interview.router import install_exception_handlers, router

app = FastAPI(
    title="SuperInsight Interview Service",
    version="1.0.0",
    docs_url="/api/interview/docs",
    openapi_url="/api/interview/openapi.json",
)

# Register unified exception handlers
install_exception_handlers(app)

# Include interview router
app.include_router(router)

# Mount Prometheus metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)
