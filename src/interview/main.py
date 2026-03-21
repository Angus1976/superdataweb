"""FastAPI application entry point for the interview service."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from prometheus_client import make_asgi_app

from src.interview.auth_router import auth_router
from src.interview.baidu_pan_router import baidu_pan_router
from src.interview.llm_config_router import llm_config_router
from src.interview.enterprise_router import enterprise_router
from src.interview.file_router import file_router
from src.interview.asr_router import asr_router
from src.interview.router import install_exception_handlers, router
from src.interview.user_router import user_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: log startup/shutdown."""
    logger.info("SuperInsight Interview Service starting up...")
    yield
    logger.info("SuperInsight Interview Service shutting down...")


app = FastAPI(
    title="SuperInsight Interview Service",
    version="1.0.0",
    docs_url="/api/interview/docs",
    openapi_url="/api/interview/openapi.json",
    lifespan=lifespan,
)

# Register unified exception handlers
install_exception_handlers(app)

# Include interview router
app.include_router(router)

# Include auth and user management routers
app.include_router(auth_router)
app.include_router(user_router)
app.include_router(enterprise_router)
app.include_router(file_router)
app.include_router(baidu_pan_router)
app.include_router(llm_config_router)
app.include_router(asr_router)

# Mount Prometheus metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# Serve frontend static files
import os
frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.exists(frontend_dist):
    app.mount("/static", StaticFiles(directory=frontend_dist), name="static")
    
    @app.get("/")
    async def serve_index():
        return FileResponse(os.path.join(frontend_dist, "index.html"))
    
    @app.get("/{path:path}")
    async def serve_frontend(path: str):
        file_path = os.path.join(frontend_dist, path)
        if os.path.exists(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(frontend_dist, "index.html"))
