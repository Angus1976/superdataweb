"""Unit tests for InterviewSecurity class."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from jose import jwt
from unittest.mock import AsyncMock, MagicMock, patch

from src.interview.config import settings
from src.interview.security import InterviewSecurity


@pytest.fixture
def security() -> InterviewSecurity:
    return InterviewSecurity()


# ---------------------------------------------------------------------------
# get_current_tenant
# ---------------------------------------------------------------------------

class TestGetCurrentTenant:
    """Tests for JWT token decoding and tenant_id extraction."""

    def test_valid_token_returns_tenant_id(self, security: InterviewSecurity):
        token = jwt.encode(
            {"tenant_id": "tenant-abc"},
            settings.JWT_SECRET,
            algorithm=settings.JWT_ALGORITHM,
        )
        assert security.get_current_tenant(token) == "tenant-abc"

    def test_invalid_token_raises_401(self, security: InterviewSecurity):
        with pytest.raises(HTTPException) as exc_info:
            security.get_current_tenant("invalid.jwt.token")
        assert exc_info.value.status_code == 401

    def test_token_missing_tenant_id_raises_401(self, security: InterviewSecurity):
        token = jwt.encode(
            {"sub": "user-1"},
            settings.JWT_SECRET,
            algorithm=settings.JWT_ALGORITHM,
        )
        with pytest.raises(HTTPException) as exc_info:
            security.get_current_tenant(token)
        assert exc_info.value.status_code == 401

    def test_expired_token_raises_401(self, security: InterviewSecurity):
        import time

        token = jwt.encode(
            {"tenant_id": "t1", "exp": int(time.time()) - 3600},
            settings.JWT_SECRET,
            algorithm=settings.JWT_ALGORITHM,
        )
        with pytest.raises(HTTPException) as exc_info:
            security.get_current_tenant(token)
        assert exc_info.value.status_code == 401

    def test_wrong_secret_raises_401(self, security: InterviewSecurity):
        token = jwt.encode(
            {"tenant_id": "t1"},
            "wrong-secret",
            algorithm=settings.JWT_ALGORITHM,
        )
        with pytest.raises(HTTPException) as exc_info:
            security.get_current_tenant(token)
        assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# sanitize_content
# ---------------------------------------------------------------------------

class TestSanitizeContent:
    """Tests for Presidio PII sanitization."""

    def test_email_is_sanitized(self, security: InterviewSecurity):
        text = "Please contact user@example.com for details."
        result = security.sanitize_content(text)
        assert "user@example.com" not in result

    def test_phone_number_is_sanitized(self, security: InterviewSecurity):
        text = "Call me at 13812345678 tomorrow."
        result = security.sanitize_content(text)
        assert "13812345678" not in result

    def test_text_without_pii_unchanged(self, security: InterviewSecurity):
        text = "This is a normal sentence with no PII."
        result = security.sanitize_content(text)
        assert result == text

    def test_empty_string_returns_empty(self, security: InterviewSecurity):
        assert security.sanitize_content("") == ""


# ---------------------------------------------------------------------------
# verify_tenant_access
# ---------------------------------------------------------------------------

class TestVerifyTenantAccess:
    """Tests for multi-tenant project access verification."""

    @pytest.mark.asyncio
    async def test_matching_tenant_returns_true(self, security: InterviewSecurity):
        mock_result = MagicMock()
        mock_result.scalar.return_value = 1

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_session
        mock_ctx.__aexit__.return_value = False

        with patch(
            "src.interview.security.async_session_factory",
            return_value=mock_ctx,
        ):
            result = await security.verify_tenant_access("tenant-1", "project-1")
        assert result is True

    @pytest.mark.asyncio
    async def test_non_matching_tenant_returns_false(self, security: InterviewSecurity):
        mock_result = MagicMock()
        mock_result.scalar.return_value = None

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_session
        mock_ctx.__aexit__.return_value = False

        with patch(
            "src.interview.security.async_session_factory",
            return_value=mock_ctx,
        ):
            result = await security.verify_tenant_access("tenant-2", "project-1")
        assert result is False
