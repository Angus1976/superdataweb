"""Unit tests for AuthService."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import bcrypt
import pytest
from fastapi import HTTPException
from jose import jwt

from src.interview.auth_service import AuthService
from src.interview.config import settings


@pytest.fixture
def auth_service() -> AuthService:
    return AuthService()


def _make_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _mock_session_factory(execute_side_effects: list):
    """Create a mock async_session_factory that returns a session with
    pre-configured execute results.

    Each call to session.execute() pops the next item from execute_side_effects.
    """
    call_idx = {"i": 0}

    mock_session = AsyncMock()

    def _execute_side_effect(*args, **kwargs):
        idx = call_idx["i"]
        call_idx["i"] += 1
        result = MagicMock()
        if idx < len(execute_side_effects):
            val = execute_side_effects[idx]
            result.fetchone.return_value = val
        else:
            result.fetchone.return_value = None
        return result

    mock_session.execute = AsyncMock(side_effect=_execute_side_effect)
    mock_session.commit = AsyncMock()

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = mock_session
    mock_ctx.__aexit__.return_value = False

    return mock_ctx, mock_session


# ---------------------------------------------------------------------------
# create_access_token
# ---------------------------------------------------------------------------


class TestCreateAccessToken:
    """Tests for JWT access token creation."""

    def test_token_contains_required_claims(self, auth_service: AuthService):
        token = auth_service.create_access_token("user-1", "tenant-1", "admin")
        payload = jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
        assert payload["user_id"] == "user-1"
        assert payload["tenant_id"] == "tenant-1"
        assert payload["role"] == "admin"
        assert "exp" in payload
        assert "iat" in payload

    def test_token_compatible_with_interview_security(self, auth_service: AuthService):
        """Token must be decodable by InterviewSecurity.get_current_tenant."""
        from src.interview.security import InterviewSecurity

        security = InterviewSecurity()
        token = auth_service.create_access_token("u1", "t1", "member")
        tenant_id = security.get_current_tenant(token)
        assert tenant_id == "t1"

    def test_token_uses_configured_algorithm(self, auth_service: AuthService):
        token = auth_service.create_access_token("u1", "t1", "member")
        header = jwt.get_unverified_header(token)
        assert header["alg"] == settings.JWT_ALGORITHM


# ---------------------------------------------------------------------------
# register
# ---------------------------------------------------------------------------


class TestRegister:
    """Tests for user registration."""

    @pytest.mark.asyncio
    async def test_register_success(self, auth_service: AuthService):
        import uuid

        user_id = str(uuid.uuid4())
        enterprise_id = str(uuid.uuid4())

        # execute calls: 1) enterprise lookup, 2) email uniqueness, 3) insert user
        execute_results = [
            (enterprise_id, "active"),  # enterprise found
            None,  # email not taken
            (user_id,),  # user created, returning id
        ]

        mock_ctx, _ = _mock_session_factory(execute_results)

        # Also mock create_refresh_token since it opens its own session
        with patch(
            "src.interview.auth_service.async_session_factory",
            return_value=mock_ctx,
        ), patch.object(
            auth_service,
            "create_refresh_token",
            new_callable=AsyncMock,
            return_value="mock-refresh-token",
        ):
            result = await auth_service.register(
                "user@corp.com", "password123", "ENT001"
            )

        assert result.access_token
        assert result.refresh_token == "mock-refresh-token"
        assert result.token_type == "bearer"
        assert result.expires_in == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

    @pytest.mark.asyncio
    async def test_register_enterprise_not_found(self, auth_service: AuthService):
        execute_results = [None]  # enterprise not found
        mock_ctx, _ = _mock_session_factory(execute_results)

        with patch(
            "src.interview.auth_service.async_session_factory",
            return_value=mock_ctx,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await auth_service.register(
                    "user@corp.com", "password123", "INVALID"
                )
            assert exc_info.value.status_code == 400
            assert "企业号不存在" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_register_email_already_exists(self, auth_service: AuthService):
        import uuid

        enterprise_id = str(uuid.uuid4())
        execute_results = [
            (enterprise_id, "active"),  # enterprise found
            (1,),  # email already exists
        ]
        mock_ctx, _ = _mock_session_factory(execute_results)

        with patch(
            "src.interview.auth_service.async_session_factory",
            return_value=mock_ctx,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await auth_service.register(
                    "user@corp.com", "password123", "ENT001"
                )
            assert exc_info.value.status_code == 400
            assert "该邮箱已被注册" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_register_enterprise_disabled(self, auth_service: AuthService):
        import uuid

        enterprise_id = str(uuid.uuid4())
        execute_results = [
            (enterprise_id, "disabled"),  # enterprise disabled
        ]
        mock_ctx, _ = _mock_session_factory(execute_results)

        with patch(
            "src.interview.auth_service.async_session_factory",
            return_value=mock_ctx,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await auth_service.register(
                    "user@corp.com", "password123", "ENT001"
                )
            assert exc_info.value.status_code == 400
            assert "企业已被禁用" in exc_info.value.detail


# ---------------------------------------------------------------------------
# login
# ---------------------------------------------------------------------------


class TestLogin:
    """Tests for user login."""

    @pytest.mark.asyncio
    async def test_login_success(self, auth_service: AuthService):
        import uuid

        user_id = str(uuid.uuid4())
        enterprise_id = str(uuid.uuid4())
        pw_hash = _make_password_hash("password123")

        execute_results = [
            (user_id, pw_hash, enterprise_id, "member", True, "active"),
        ]
        mock_ctx, _ = _mock_session_factory(execute_results)

        with patch(
            "src.interview.auth_service.async_session_factory",
            return_value=mock_ctx,
        ), patch.object(
            auth_service,
            "create_refresh_token",
            new_callable=AsyncMock,
            return_value="mock-refresh-token",
        ):
            result = await auth_service.login("user@corp.com", "password123")

        assert result.access_token
        assert result.refresh_token == "mock-refresh-token"
        assert result.token_type == "bearer"

    @pytest.mark.asyncio
    async def test_login_user_not_found(self, auth_service: AuthService):
        execute_results = [None]
        mock_ctx, _ = _mock_session_factory(execute_results)

        with patch(
            "src.interview.auth_service.async_session_factory",
            return_value=mock_ctx,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await auth_service.login("unknown@corp.com", "password123")
            assert exc_info.value.status_code == 401
            assert "邮箱或密码错误" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, auth_service: AuthService):
        import uuid

        user_id = str(uuid.uuid4())
        enterprise_id = str(uuid.uuid4())
        pw_hash = _make_password_hash("correct-password")

        execute_results = [
            (user_id, pw_hash, enterprise_id, "member", True, "active"),
        ]
        mock_ctx, _ = _mock_session_factory(execute_results)

        with patch(
            "src.interview.auth_service.async_session_factory",
            return_value=mock_ctx,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await auth_service.login("user@corp.com", "wrong-password")
            assert exc_info.value.status_code == 401
            assert "邮箱或密码错误" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_login_enterprise_disabled(self, auth_service: AuthService):
        import uuid

        user_id = str(uuid.uuid4())
        enterprise_id = str(uuid.uuid4())
        pw_hash = _make_password_hash("password123")

        execute_results = [
            (user_id, pw_hash, enterprise_id, "member", True, "disabled"),
        ]
        mock_ctx, _ = _mock_session_factory(execute_results)

        with patch(
            "src.interview.auth_service.async_session_factory",
            return_value=mock_ctx,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await auth_service.login("user@corp.com", "password123")
            assert exc_info.value.status_code == 401
            assert "企业已被禁用" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_login_user_disabled(self, auth_service: AuthService):
        import uuid

        user_id = str(uuid.uuid4())
        enterprise_id = str(uuid.uuid4())
        pw_hash = _make_password_hash("password123")

        execute_results = [
            (user_id, pw_hash, enterprise_id, "member", False, "active"),
        ]
        mock_ctx, _ = _mock_session_factory(execute_results)

        with patch(
            "src.interview.auth_service.async_session_factory",
            return_value=mock_ctx,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await auth_service.login("user@corp.com", "password123")
            assert exc_info.value.status_code == 401
            assert "账号已被禁用" in exc_info.value.detail


# ---------------------------------------------------------------------------
# refresh_token
# ---------------------------------------------------------------------------


class TestRefreshToken:
    """Tests for token refresh."""

    @pytest.mark.asyncio
    async def test_refresh_success(self, auth_service: AuthService):
        import uuid

        raw_token = "test-refresh-token"
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        token_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        enterprise_id = str(uuid.uuid4())
        expires_at = datetime.now(timezone.utc) + timedelta(days=1)

        execute_results = [
            (token_id, user_id, False, expires_at),  # token record
            None,  # update is_used
            (user_id, enterprise_id, "member"),  # user lookup
        ]
        mock_ctx, _ = _mock_session_factory(execute_results)

        with patch(
            "src.interview.auth_service.async_session_factory",
            return_value=mock_ctx,
        ), patch.object(
            auth_service,
            "create_refresh_token",
            new_callable=AsyncMock,
            return_value="new-refresh-token",
        ):
            result = await auth_service.refresh_token(raw_token)

        assert result.access_token
        assert result.refresh_token == "new-refresh-token"

    @pytest.mark.asyncio
    async def test_refresh_token_not_found(self, auth_service: AuthService):
        execute_results = [None]
        mock_ctx, _ = _mock_session_factory(execute_results)

        with patch(
            "src.interview.auth_service.async_session_factory",
            return_value=mock_ctx,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await auth_service.refresh_token("invalid-token")
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_token_already_used(self, auth_service: AuthService):
        import uuid

        token_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        expires_at = datetime.now(timezone.utc) + timedelta(days=1)

        execute_results = [
            (token_id, user_id, True, expires_at),  # is_used=True
        ]
        mock_ctx, _ = _mock_session_factory(execute_results)

        with patch(
            "src.interview.auth_service.async_session_factory",
            return_value=mock_ctx,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await auth_service.refresh_token("some-token")
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_token_expired(self, auth_service: AuthService):
        import uuid

        token_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        expires_at = datetime.now(timezone.utc) - timedelta(hours=1)

        execute_results = [
            (token_id, user_id, False, expires_at),  # expired
        ]
        mock_ctx, _ = _mock_session_factory(execute_results)

        with patch(
            "src.interview.auth_service.async_session_factory",
            return_value=mock_ctx,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await auth_service.refresh_token("some-token")
            assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# revoke_refresh_token
# ---------------------------------------------------------------------------


class TestRevokeRefreshToken:
    """Tests for token revocation."""

    @pytest.mark.asyncio
    async def test_revoke_marks_token_as_used(self, auth_service: AuthService):
        execute_results = [None]  # update result
        mock_ctx, mock_session = _mock_session_factory(execute_results)

        with patch(
            "src.interview.auth_service.async_session_factory",
            return_value=mock_ctx,
        ):
            await auth_service.revoke_refresh_token("some-token")

        # Verify execute was called (the UPDATE query)
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()
