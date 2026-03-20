"""FastAPI application entry point for the interview service."""

from __future__ import annotations

from fastapi import FastAPI
from prometheus_client import make_asgi_app

from src.interview.auth_router import auth_router
from src.interview.baidu_pan_router import baidu_pan_router
from src.interview.llm_config_router import llm_config_router
from src.interview.enterprise_router import enterprise_router
from src.interview.file_router import file_router
from src.interview.asr_router import asr_router
from src.interview.router import install_exception_handlers, router
from src.interview.user_router import user_router

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
