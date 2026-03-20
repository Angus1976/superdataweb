"""Unit tests for llm_config_router.py — auth helpers and config endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from jose import jwt

from src.interview.config import settings
from src.interview.llm_config_router import _get_user_info, _require_admin
from src.interview.llm_models import (
    ConnectivityResult,
    LLMConfigResponse,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_token(
    user_id: str = "u1",
    tenant_id: str = "t1",
    role: str = "admin",
    expired: bool = False,
) -> str:
    now = datetime.now(timezone.utc)
    exp = now - timedelta(hours=1) if expired else now + timedelta(hours=1)
    payload = {
        "user_id": user_id,
        "tenant_id": tenant_id,
        "role": role,
        "exp": exp,
        "iat": now,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


# ---------------------------------------------------------------------------
# _get_user_info tests
# ---------------------------------------------------------------------------

class TestGetUserInfo:
    @pytest.mark.asyncio
    async def test_valid_token(self):
        token = _make_token(user_id="u1", tenant_id="t1", role="admin")
        result = await _get_user_info(token=token)
        assert result["user_id"] == "u1"
        assert result["tenant_id"] == "t1"
        assert result["role"] == "admin"

    @pytest.mark.asyncio
    async def test_invalid_token_raises_401(self):
        with pytest.raises(Exception) as exc_info:
            await _get_user_info(token="not-a-real-token")
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_expired_token_raises_401(self):
        token = _make_token(expired=True)
        with pytest.raises(Exception) as exc_info:
            await _get_user_info(token=token)
        assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# _require_admin tests
# ---------------------------------------------------------------------------

class TestRequireAdmin:
    def test_admin_passes(self):
        _require_admin({"user_id": "u1", "tenant_id": "t1", "role": "admin"})

    def test_member_raises_403(self):
        with pytest.raises(Exception) as exc_info:
            _require_admin({"user_id": "u1", "tenant_id": "t1", "role": "member"})
        assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# Endpoint integration tests
# ---------------------------------------------------------------------------

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.interview.llm_config_router import llm_config_router

_app = FastAPI()
_app.include_router(llm_config_router)


def _admin_headers() -> dict:
    token = _make_token(user_id="u1", tenant_id="t1", role="admin")
    return {"Authorization": f"Bearer {token}"}


def _member_headers() -> dict:
    token = _make_token(user_id="u2", tenant_id="t1", role="member")
    return {"Authorization": f"Bearer {token}"}


_FAKE_RESPONSE = LLMConfigResponse(
    configured=True,
    provider_name="openai",
    api_key_masked="sk-t****abcd",
    base_url="https://api.openai.com/v1",
    model_name="gpt-3.5-turbo",
    temperature=0.7,
    max_tokens=2048,
)

_FAKE_CONNECTIVITY = ConnectivityResult(
    ok=True,
    message="连接成功",
    model="gpt-3.5-turbo",
    response_time_ms=123,
)


class TestEndpoints:
    @pytest.mark.asyncio
    async def test_save_config_admin(self):
        with patch(
            "src.interview.llm_config_router._svc.save_config",
            new_callable=AsyncMock,
            return_value=_FAKE_RESPONSE,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=_app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/api/llm-config/config",
                    json={
                        "provider_name": "openai",
                        "api_key": "sk-test1234567890abcd",
                        "base_url": "https://api.openai.com/v1",
                        "model_name": "gpt-3.5-turbo",
                        "temperature": 0.7,
                        "max_tokens": 2048,
                    },
                    headers=_admin_headers(),
                )
            assert resp.status_code == 200
            body = resp.json()
            assert body["configured"] is True
            assert body["provider_name"] == "openai"
            assert body["api_key_masked"] == "sk-t****abcd"

    @pytest.mark.asyncio
    async def test_save_config_member_forbidden(self):
        async with AsyncClient(
            transport=ASGITransport(app=_app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/llm-config/config",
                json={
                    "provider_name": "openai",
                    "api_key": "sk-test1234567890abcd",
                    "base_url": "https://api.openai.com/v1",
                    "model_name": "gpt-3.5-turbo",
                },
                headers=_member_headers(),
            )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_get_config_admin(self):
        with patch(
            "src.interview.llm_config_router._svc.get_config",
            new_callable=AsyncMock,
            return_value=_FAKE_RESPONSE,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=_app), base_url="http://test"
            ) as client:
                resp = await client.get(
                    "/api/llm-config/config",
                    headers=_admin_headers(),
                )
            assert resp.status_code == 200
            body = resp.json()
            assert body["configured"] is True
            assert body["api_key_masked"] == "sk-t****abcd"

    @pytest.mark.asyncio
    async def test_get_config_not_configured(self):
        with patch(
            "src.interview.llm_config_router._svc.get_config",
            new_callable=AsyncMock,
            return_value=LLMConfigResponse(configured=False),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=_app), base_url="http://test"
            ) as client:
                resp = await client.get(
                    "/api/llm-config/config",
                    headers=_admin_headers(),
                )
            assert resp.status_code == 200
            assert resp.json()["configured"] is False

    @pytest.mark.asyncio
    async def test_test_connectivity_admin(self):
        with patch(
            "src.interview.llm_config_router._svc.test_connectivity",
            new_callable=AsyncMock,
            return_value=_FAKE_CONNECTIVITY,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=_app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/api/llm-config/config/test",
                    json={
                        "provider_name": "openai",
                        "api_key": "sk-test1234567890abcd",
                        "base_url": "https://api.openai.com/v1",
                        "model_name": "gpt-3.5-turbo",
                    },
                    headers=_admin_headers(),
                )
            assert resp.status_code == 200
            body = resp.json()
            assert body["ok"] is True
            assert body["message"] == "连接成功"
            assert body["response_time_ms"] == 123

    @pytest.mark.asyncio
    async def test_test_connectivity_member_forbidden(self):
        async with AsyncClient(
            transport=ASGITransport(app=_app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/llm-config/config/test",
                json={
                    "provider_name": "openai",
                    "api_key": "sk-test1234567890abcd",
                    "base_url": "https://api.openai.com/v1",
                    "model_name": "gpt-3.5-turbo",
                },
                headers=_member_headers(),
            )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_no_auth_header(self):
        async with AsyncClient(
            transport=ASGITransport(app=_app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/llm-config/config")
        # FastAPI returns 401 for missing OAuth2 token
        assert resp.status_code == 401
