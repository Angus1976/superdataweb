"""Tests for the interview router – error handling, dependencies, health check."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI, HTTPException, status
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from jose import jwt
from pydantic import ValidationError

from src.interview.config import settings
from src.interview.router import (
    ErrorResponse,
    _STATUS_ERROR_MAP,
    get_current_tenant,
    http_exception_handler,
    install_exception_handlers,
    router,
    verify_project_access,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_token(tenant_id: str = "tenant-1") -> str:
    return jwt.encode(
        {"tenant_id": tenant_id},
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )


@pytest.fixture()
def app() -> FastAPI:
    app = FastAPI()
    install_exception_handlers(app)
    app.include_router(router)
    return app


@pytest.fixture()
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------------------
# ErrorResponse model
# ---------------------------------------------------------------------------

class TestErrorResponse:
    def test_default_request_id(self):
        resp = ErrorResponse(error="test", message="msg")
        assert resp.request_id  # non-empty UUID hex

    def test_custom_fields(self):
        resp = ErrorResponse(
            error="not_found",
            message="Resource missing",
            details={"id": "123"},
            request_id="abc",
        )
        assert resp.error == "not_found"
        assert resp.details == {"id": "123"}
        assert resp.request_id == "abc"


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

class TestHealthCheck:
    def test_health_ok(self, client: TestClient):
        resp = client.get("/api/interview/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------

class TestExceptionHandlers:
    def test_http_exception_401(self, app: FastAPI, client: TestClient):
        @app.get("/test-401")
        async def _():
            raise HTTPException(status_code=401, detail="bad token")

        resp = client.get("/test-401")
        assert resp.status_code == 401
        body = resp.json()
        assert body["error"] == "unauthorized"
        assert body["message"] == "bad token"
        assert "request_id" in body

    def test_http_exception_403(self, app: FastAPI, client: TestClient):
        @app.get("/test-403")
        async def _():
            raise HTTPException(status_code=403, detail="no access")

        resp = client.get("/test-403")
        assert resp.status_code == 403
        assert resp.json()["error"] == "forbidden"

    def test_http_exception_404(self, app: FastAPI, client: TestClient):
        @app.get("/test-404")
        async def _():
            raise HTTPException(status_code=404, detail="gone")

        resp = client.get("/test-404")
        assert resp.status_code == 404
        assert resp.json()["error"] == "not_found"

    def test_http_exception_409(self, app: FastAPI, client: TestClient):
        @app.get("/test-409")
        async def _():
            raise HTTPException(status_code=409, detail="conflict")

        resp = client.get("/test-409")
        assert resp.status_code == 409
        assert resp.json()["error"] == "conflict"

    def test_http_exception_502(self, app: FastAPI, client: TestClient):
        @app.get("/test-502")
        async def _():
            raise HTTPException(status_code=502, detail="upstream down")

        resp = client.get("/test-502")
        assert resp.status_code == 502
        assert resp.json()["error"] == "bad_gateway"

    def test_http_exception_504(self, app: FastAPI, client: TestClient):
        @app.get("/test-504")
        async def _():
            raise HTTPException(status_code=504, detail="timeout")

        resp = client.get("/test-504")
        assert resp.status_code == 504
        assert resp.json()["error"] == "gateway_timeout"

    def test_validation_error(self, app: FastAPI, client: TestClient):
        from pydantic import BaseModel

        class Body(BaseModel):
            name: str
            age: int

        @app.post("/test-validation")
        async def _(body: Body):
            return body

        resp = client.post("/test-validation", json={"name": 123})
        assert resp.status_code == 422
        body = resp.json()
        assert body["error"] == "validation_error"
        assert "errors" in body["details"]


# ---------------------------------------------------------------------------
# get_current_tenant dependency
# ---------------------------------------------------------------------------

class TestGetCurrentTenant:
    @pytest.mark.asyncio
    async def test_valid_token(self):
        token = _make_token("t-abc")
        tenant = await get_current_tenant(token)
        assert tenant == "t-abc"

    @pytest.mark.asyncio
    async def test_invalid_token(self):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_tenant("bad.token.here")
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_missing_tenant_claim(self):
        token = jwt.encode(
            {"sub": "user1"},
            settings.JWT_SECRET,
            algorithm=settings.JWT_ALGORITHM,
        )
        with pytest.raises(HTTPException) as exc_info:
            await get_current_tenant(token)
        assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# verify_project_access dependency
# ---------------------------------------------------------------------------

class TestVerifyProjectAccess:
    @pytest.mark.asyncio
    async def test_access_granted(self):
        with patch(
            "src.interview.router._security.verify_tenant_access",
            new_callable=AsyncMock,
            return_value=True,
        ):
            result = await verify_project_access("proj-1", "tenant-1")
            assert result == "tenant-1"

    @pytest.mark.asyncio
    async def test_access_denied(self):
        with patch(
            "src.interview.router._security.verify_tenant_access",
            new_callable=AsyncMock,
            return_value=False,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await verify_project_access("proj-1", "tenant-1")
            assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# Status-error mapping completeness
# ---------------------------------------------------------------------------

class TestStatusErrorMap:
    def test_all_expected_codes_mapped(self):
        expected = {401, 403, 404, 400, 409, 422, 502, 504}
        assert expected == set(_STATUS_ERROR_MAP.keys())
