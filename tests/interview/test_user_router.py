"""Unit tests for user_router.py — JWT auth dependencies and admin endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from jose import jwt

from src.interview.auth_models import (
    BatchImportResult,
    PaginatedUsers,
    UserResponse,
)
from src.interview.config import settings
from src.interview.user_router import get_current_user, require_admin


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_token(
    user_id: str = "u1",
    tenant_id: str = "t1",
    role: str = "admin",
    expired: bool = False,
) -> str:
    """Create a JWT token for testing."""
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
# get_current_user tests
# ---------------------------------------------------------------------------

class TestGetCurrentUser:
    """Tests for the get_current_user dependency."""

    @pytest.mark.asyncio
    async def test_valid_token(self):
        token = _make_token(user_id="u1", tenant_id="t1", role="admin")
        result = await get_current_user(authorization=f"Bearer {token}")
        assert result["user_id"] == "u1"
        assert result["tenant_id"] == "t1"
        assert result["role"] == "admin"

    @pytest.mark.asyncio
    async def test_missing_bearer_prefix(self):
        token = _make_token()
        with pytest.raises(Exception) as exc_info:
            await get_current_user(authorization=token)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_expired_token(self):
        token = _make_token(expired=True)
        with pytest.raises(Exception) as exc_info:
            await get_current_user(authorization=f"Bearer {token}")
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_token(self):
        with pytest.raises(Exception) as exc_info:
            await get_current_user(authorization="Bearer not-a-real-token")
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_token_missing_claims(self):
        """Token with missing user_id/tenant_id/role should raise 401."""
        now = datetime.now(timezone.utc)
        payload = {"exp": now + timedelta(hours=1), "iat": now}
        token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
        with pytest.raises(Exception) as exc_info:
            await get_current_user(authorization=f"Bearer {token}")
        assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# require_admin tests
# ---------------------------------------------------------------------------

class TestRequireAdmin:
    """Tests for the require_admin dependency."""

    @pytest.mark.asyncio
    async def test_admin_allowed(self):
        user = {"user_id": "u1", "tenant_id": "t1", "role": "admin"}
        result = await require_admin(current_user=user)
        assert result == user

    @pytest.mark.asyncio
    async def test_member_forbidden(self):
        user = {"user_id": "u1", "tenant_id": "t1", "role": "member"}
        with pytest.raises(Exception) as exc_info:
            await require_admin(current_user=user)
        assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# Endpoint tests (using FastAPI TestClient)
# ---------------------------------------------------------------------------

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.interview.user_router import user_router

_app = FastAPI()
_app.include_router(user_router)


def _admin_headers() -> dict:
    token = _make_token(user_id="u1", tenant_id="t1", role="admin")
    return {"Authorization": f"Bearer {token}"}


def _member_headers() -> dict:
    token = _make_token(user_id="u2", tenant_id="t1", role="member")
    return {"Authorization": f"Bearer {token}"}


_FAKE_USER = UserResponse(
    id="uid1",
    email="test@corp.com",
    role="member",
    is_active=True,
    created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
)


class TestEndpoints:
    """Integration-style tests for user_router endpoints."""

    @pytest.mark.asyncio
    async def test_list_users_admin(self):
        fake_result = PaginatedUsers(items=[_FAKE_USER], total=1, page=1, size=20)
        with patch.object(
            type(_app.router),
            "__init__",
            lambda *a, **kw: None,
        ):
            pass
        with patch(
            "src.interview.user_router._user_service.list_users",
            new_callable=AsyncMock,
            return_value=fake_result,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=_app), base_url="http://test"
            ) as client:
                resp = await client.get("/api/users", headers=_admin_headers())
            assert resp.status_code == 200
            body = resp.json()
            assert body["total"] == 1
            assert len(body["items"]) == 1

    @pytest.mark.asyncio
    async def test_list_users_member_forbidden(self):
        async with AsyncClient(
            transport=ASGITransport(app=_app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/users", headers=_member_headers())
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_create_user_admin(self):
        with patch(
            "src.interview.user_router._user_service.create_user",
            new_callable=AsyncMock,
            return_value=_FAKE_USER,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=_app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/api/users",
                    json={"email": "new@corp.com", "password": "12345678", "role": "member"},
                    headers=_admin_headers(),
                )
            assert resp.status_code == 200
            assert resp.json()["email"] == "test@corp.com"

    @pytest.mark.asyncio
    async def test_update_user_admin(self):
        with patch(
            "src.interview.user_router._user_service.update_user",
            new_callable=AsyncMock,
            return_value=_FAKE_USER,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=_app), base_url="http://test"
            ) as client:
                resp = await client.put(
                    "/api/users/uid1",
                    json={"role": "admin"},
                    headers=_admin_headers(),
                )
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_delete_user_admin(self):
        with patch(
            "src.interview.user_router._user_service.delete_user",
            new_callable=AsyncMock,
            return_value=None,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=_app), base_url="http://test"
            ) as client:
                resp = await client.delete(
                    "/api/users/uid1",
                    headers=_admin_headers(),
                )
            assert resp.status_code == 200
            assert resp.json()["detail"] == "用户已删除"

    @pytest.mark.asyncio
    async def test_no_auth_header(self):
        async with AsyncClient(
            transport=ASGITransport(app=_app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/users")
        assert resp.status_code == 422  # missing required header

    @pytest.mark.asyncio
    async def test_batch_import_unsupported_format(self):
        """Uploading a .txt file should return an error result."""
        with patch(
            "src.interview.user_router._user_service.batch_import",
            new_callable=AsyncMock,
        ) as mock_import:
            async with AsyncClient(
                transport=ASGITransport(app=_app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/api/users/batch-import",
                    files={"file": ("users.txt", b"data", "text/plain")},
                    headers=_admin_headers(),
                )
            assert resp.status_code == 200
            body = resp.json()
            assert body["success_count"] == 0
            assert body["failure_count"] == 1
            mock_import.assert_not_called()

    @pytest.mark.asyncio
    async def test_batch_import_csv(self):
        fake_result = BatchImportResult(success_count=2, failure_count=0, errors=[])
        with patch(
            "src.interview.user_router._user_service.batch_import",
            new_callable=AsyncMock,
            return_value=fake_result,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=_app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/api/users/batch-import",
                    files={"file": ("users.csv", b"email,password\na@b.com,12345678", "text/csv")},
                    headers=_admin_headers(),
                )
            assert resp.status_code == 200
            assert resp.json()["success_count"] == 2
